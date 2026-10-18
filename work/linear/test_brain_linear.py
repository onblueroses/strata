"""Offline check that pickup queries the configured decision team."""
import contextlib
import importlib.machinery
import importlib.util
import io
import os
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parent / "brain-linear"


class PickupRouting(unittest.TestCase):
    def test_decision_team_comes_from_environment(self):
        with patch.dict(os.environ, {"BRAIN_LINEAR_DECISION_TEAM_KEY": "SAMPLE"}):
            loader = importlib.machinery.SourceFileLoader("brain_linear_fixture", str(SCRIPT))
            module = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
            loader.exec_module(module)
        filters = []
        def fetch(_auth, issue_filter, _query=None):
            filters.append(issue_filter)
            return []
        with patch.object(module, "fetch_all_issues", side_effect=fetch), contextlib.redirect_stdout(io.StringIO()):
            module.cmd_pickup(object(), ["codex"])
        self.assertEqual(filters[1]["team"]["key"]["eq"], "SAMPLE")


if __name__ == "__main__":
    unittest.main()
