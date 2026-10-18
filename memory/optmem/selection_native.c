/* CPython boundary for Bend 2.0.32's private emitted CPU runtime.
 * Selection and certificate logic live entirely in the generated program.
 * The builder pins runtime fragments for fail-stop translation, CPU stack
 * bounds, and bounded/signal-aware evaluation.
 */
#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <setjmp.h>
#include <sys/mman.h>
#include <unistd.h>
#define BRIDGE_STACK_WORDS (1u << 20)
#define BRIDGE_SPAN (1ull << 30)
#define BRIDGE_STEP_LIMIT 200000000ull
static jmp_buf bridge_jump;
static const char *bridge_error;
static unsigned long long bridge_steps;
static int bridge_active;
static _Noreturn void bridge_fail(const char *msg) {
  bridge_error = msg;
  longjmp(bridge_jump, 1);
}
static inline void bridge_step(void) {
  if (++bridge_steps > BRIDGE_STEP_LIMIT) bridge_fail("selection evaluation resource limit");
  if ((bridge_steps & 16383u) == 0 && PyErr_CheckSignals() < 0)
    bridge_fail("selection interrupted");
}
#define main bend_unused_main
#include "selection.generated.c"
#undef main

static u64 *bridge_corpus;
static Env bridge_env;
static pid_t bridge_pid;

static void bridge_clear(void) {
  if (bridge_corpus) munmap(bridge_corpus, BRIDGE_SPAN);
  free(io_stk);
  io_stk = NULL;
  bridge_corpus = NULL;
  CORPUS = NULL;
  corpus_size = 0;
  memset(ALC, 0, sizeof(ALC));
  bridge_pid = 0;
}

static int bridge_setup(void) {
  if (bridge_pid && bridge_pid != getpid()) bridge_clear();
  if (bridge_corpus) return 0;
  void *mem = mmap(NULL, BRIDGE_SPAN, PROT_READ | PROT_WRITE,
                  MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
  if (mem == MAP_FAILED) {PyErr_SetFromErrno(PyExc_OSError); return -1;}
  bridge_corpus = CORPUS = mem;
  corpus_size = BRIDGE_SPAN;
  io_stk = calloc(BRIDGE_STACK_WORDS, sizeof(Term));
  if (!io_stk) {bridge_clear(); PyErr_NoMemory(); return -1;}
  const u64 cap = (BRIDGE_SPAN / 8 - HEAP_OFF) / (PAGE_LEN + 10);
  KEEP_WORDS = CAP_WORDS;
  memcpy(CORPUS + STAT_OFF, STAT_IMG, STAT_LEN * sizeof(u64));
  u64 at = HEAP_OFF + (cap << PAGE_BITS);
  for (u32 c = 0; c < NCLS_ALL; c++) {
    bank_at(CORPUS, c)->off = at;
    at += 2 * (cap >> ((c < NCLS ? NCLS : c) - PAGE_BITS));
  }
  a32_store(a32_at(CORPUS, H_BUMP), 1);
  a32_store(a32_at(CORPUS, H_CAP), (u32)cap);
  pool_size = 1;
  io_gpu = false;
  bridge_env = (Env){CORPUS, ALC[0]};
  bridge_pid = getpid();
  return 0;
}

static PyObject *cover_impl(PyObject *args, int with_status) {
  PyObject *total_obj, *budget_obj;
  if (!PyArg_ParseTuple(args, "OO", &total_obj, &budget_obj)) return NULL;
  if (!PyLong_CheckExact(total_obj) || !PyLong_CheckExact(budget_obj)) {
    PyErr_SetString(PyExc_ValueError, "total and budget must be exact integers"); return NULL;
  }
  unsigned long long t = PyLong_AsUnsignedLongLong(total_obj);
  if (PyErr_Occurred()) return NULL;
  unsigned long long b = PyLong_AsUnsignedLongLong(budget_obj);
  if (PyErr_Occurred()) return NULL;
  if (t > UINT32_MAX || !b || b > UINT32_MAX || (t < b ? t : b) > 65535) {
    PyErr_SetString(PyExc_ValueError, "requires U32 total, positive U32 budget, at most 65535 requested blocks");
    return NULL;
  }
  if (bridge_active) {
    PyErr_SetString(PyExc_RuntimeError, "recursive Bend selector call during evaluation");
    return NULL;
  }
  uint32_t expected = (uint32_t)(t < b ? t : b);
  uint32_t minimal = __builtin_popcount((uint32_t)t);
  if (expected < minimal) expected = minimal;
  if (PyErr_CheckSignals() < 0 || bridge_setup() < 0) return NULL;
  uint32_t *depths = PyMem_Malloc((expected ? expected : 1) * sizeof(uint32_t));
  if (!depths) return PyErr_NoMemory();
  if (setjmp(bridge_jump)) {
    bridge_active = 0;
    PyMem_Free(depths);
    bridge_clear();
    if (!PyErr_Occurred()) PyErr_SetString(PyExc_RuntimeError,
      bridge_error ? bridge_error : "Bend runtime failed");
    return NULL;
  }
  /* Nat and U32 are immediate numeric Terms in the pinned emitter. */
  Term argv[] = {1, t ? 31u - __builtin_clz((uint32_t)t) : 0, 32, t, b};
  bridge_steps = 0;
  bridge_active = 1;
  if (fid_arity(FID_ENTRY_STATUS) != 5) bridge_fail("unexpected Bend status entry arity");
  u64 a = task_node(bridge_env, FID_ENTRY_STATUS, TERM_HOLE, 0, 0);
  for (u32 i = 0; i < 5; i++) bridge_env.mem[a+i] = argv[i];
  /* This pinned emitter flattens (U32, Maybe<Chunks>) into three root words. */
  Term status = corpus_eval(bridge_corpus, term_tsk(FID_ENTRY_STATUS, a));
  if (status > 2) bridge_fail("invalid Bend selection status");
  Term accepted = bridge_corpus[H_ROOT_WORD + 1];
  if (accepted != 1) bridge_fail("Bend certificate rejected the selection");
  Term result = bridge_corpus[H_ROOT_WORD + 2];
  Term cursor = result;
  uint32_t n = 0;
  uint64_t lo = 0, previous = 1ull << 32;
  while (term_aux(cursor) == CID_SELECTION_MORE && term_tag(cursor) == TAG_CTR) {
    if (n >= expected) bridge_fail("Bend returned too many blocks");
    u64 p = term_peek(bridge_env.mem, cursor);
    Term d = bridge_env.mem[p];
    if (d > 31) bridge_fail("invalid Bend block depth");
    uint64_t width = 1ull << d;
    if (lo % width || lo + width > t || width > previous)
      bridge_fail("invalid Bend alignment, extent or recency");
    depths[n++] = (uint32_t)d;
    lo += width;
    previous = width;
    cursor = bridge_env.mem[p+1];
  }
  if (term_tag(cursor) != TAG_PAK || term_aux(cursor) != CID_SELECTION_END || n != expected || lo != t)
    bridge_fail("invalid Bend coverage or block count");
  term_drop(bridge_env, result);
  if (PyErr_CheckSignals() < 0) {bridge_active = 0; PyMem_Free(depths); return NULL;}
  PyObject *out = PyList_New(expected);
  if (!out) {bridge_active = 0; PyMem_Free(depths); return NULL;}
  lo = 0;
  for (uint32_t i = 0; i < expected; i++) {
    uint64_t end = lo + (1ull << depths[i]);
    PyObject *item = Py_BuildValue("(KK)", (unsigned long long)lo, (unsigned long long)end);
    if (!item) {bridge_active = 0; PyMem_Free(depths); Py_DECREF(out); return NULL;}
    PyList_SET_ITEM(out, i, item);
    lo = end;
  }
  PyMem_Free(depths);
  bridge_active = 0;
  if (!with_status) return out;
  PyObject *tag = PyLong_FromUnsignedLong((unsigned long)status);
  if (!tag) {Py_DECREF(out); return NULL;}
  PyObject *pair = PyTuple_New(2);
  if (!pair) {Py_DECREF(tag); Py_DECREF(out); return NULL;}
  PyTuple_SET_ITEM(pair, 0, tag);
  PyTuple_SET_ITEM(pair, 1, out);
  return pair;
}

static PyObject *cover_py(PyObject *self, PyObject *args) {
  (void)self;
  return cover_impl(args, 0);
}

static PyObject *cover_status_py(PyObject *self, PyObject *args) {
  (void)self;
  return cover_impl(args, 1);
}

static PyObject *stats_py(PyObject *self, PyObject *unused) {
  (void)self; (void)unused;
  return Py_BuildValue("(KK)", (unsigned long long)bridge_pid,
    bridge_corpus ? (unsigned long long)a32_load(a32_at(bridge_corpus, H_BUMP)) : 0ull);
}
static PyObject *steps_py(PyObject *self, PyObject *unused) {
  (void)self; (void)unused;
  return PyLong_FromUnsignedLongLong(bridge_steps);
}
static void module_free(void *module) {(void)module; bridge_clear();}
static PyMethodDef methods[] = {
  {"cover", cover_py, METH_VARARGS, "Return a mandatory Bend-certified aligned partition."},
  {"cover_status", cover_status_py, METH_VARARGS, "Return the checked selection path and partition."},
  {"_stats", stats_py, METH_NOARGS, "PID and allocator pages for lifecycle tests."},
  {"_steps", steps_py, METH_NOARGS, "Evaluation steps in the last request."},
  {NULL, NULL, 0, NULL}
};
static struct PyModuleDef module = {
  PyModuleDef_HEAD_INIT, "_optmem_selection", NULL, -1, methods,
  NULL, NULL, NULL, module_free
};
PyMODINIT_FUNC PyInit__optmem_selection(void) {
  if (PyInterpreterState_GetID(PyInterpreterState_Get()) != 0) {
    PyErr_SetString(PyExc_ImportError, "OptMem's pinned CPU runtime requires the main interpreter");
    return NULL;
  }
  return PyModule_Create(&module);
}
