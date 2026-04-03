use std::collections::HashMap;
use std::fmt;
use std::path::Path;

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Language {
    Rust,
    TypeScript,
    JavaScript,
    Python,
    Go,
    Java,
    Unknown,
}

impl fmt::Display for Language {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Rust => write!(f, "Rust"),
            Self::TypeScript => write!(f, "TypeScript"),
            Self::JavaScript => write!(f, "JavaScript"),
            Self::Python => write!(f, "Python"),
            Self::Go => write!(f, "Go"),
            Self::Java => write!(f, "Java"),
            Self::Unknown => write!(f, "Unknown"),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Framework {
    // JS/TS
    Nextjs,
    React,
    Vue,
    Svelte,
    Express,
    Nestjs,
    // Rust
    Axum,
    Actix,
    Rocket,
    // Python
    Django,
    Flask,
    FastApi,
    // Go
    Gin,
    Echo,
    // Java
    Spring,
}

impl fmt::Display for Framework {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Nextjs => write!(f, "Next.js"),
            Self::React => write!(f, "React"),
            Self::Vue => write!(f, "Vue"),
            Self::Svelte => write!(f, "Svelte"),
            Self::Express => write!(f, "Express"),
            Self::Nestjs => write!(f, "NestJS"),
            Self::Axum => write!(f, "Axum"),
            Self::Actix => write!(f, "Actix"),
            Self::Rocket => write!(f, "Rocket"),
            Self::Django => write!(f, "Django"),
            Self::Flask => write!(f, "Flask"),
            Self::FastApi => write!(f, "FastAPI"),
            Self::Gin => write!(f, "Gin"),
            Self::Echo => write!(f, "Echo"),
            Self::Spring => write!(f, "Spring"),
        }
    }
}

#[derive(Debug, Clone)]
pub struct ProjectType {
    pub language: Language,
    pub frameworks: Vec<Framework>,
    pub build_tool: Option<String>,
}

impl ProjectType {
    pub fn unknown() -> Self {
        Self {
            language: Language::Unknown,
            frameworks: Vec::new(),
            build_tool: None,
        }
    }
}

/// Detect project type from marker files at `root`.
/// Priority: Cargo.toml > package.json+tsconfig > pyproject.toml > go.mod > pom.xml/build.gradle.
/// Falls back to file extension frequency from `files`.
pub fn detect_project_type(root: &Path, files: &[std::path::PathBuf]) -> ProjectType {
    // Rust
    if root.join("Cargo.toml").exists() {
        let frameworks = detect_rust_frameworks(root);
        return ProjectType {
            language: Language::Rust,
            frameworks,
            build_tool: Some("Cargo".to_string()),
        };
    }

    // TypeScript / JavaScript
    if root.join("package.json").exists() {
        let is_ts = root.join("tsconfig.json").exists() || root.join("tsconfig.base.json").exists();
        let frameworks = detect_js_frameworks(root);
        let build_tool = detect_js_build_tool(root);
        return ProjectType {
            language: if is_ts {
                Language::TypeScript
            } else {
                Language::JavaScript
            },
            frameworks,
            build_tool: Some(build_tool),
        };
    }

    // Python
    if root.join("pyproject.toml").exists()
        || root.join("setup.py").exists()
        || root.join("requirements.txt").exists()
    {
        let frameworks = detect_python_frameworks(root);
        let build_tool = if root.join("pyproject.toml").exists() {
            detect_python_build_tool(root)
        } else if root.join("setup.py").exists() {
            "setuptools".to_string()
        } else {
            "pip".to_string()
        };
        return ProjectType {
            language: Language::Python,
            frameworks,
            build_tool: Some(build_tool),
        };
    }

    // Go
    if root.join("go.mod").exists() {
        let frameworks = detect_go_frameworks(root);
        return ProjectType {
            language: Language::Go,
            frameworks,
            build_tool: Some("go".to_string()),
        };
    }

    // Java
    if root.join("pom.xml").exists() {
        let frameworks = detect_java_frameworks(root, "pom.xml");
        return ProjectType {
            language: Language::Java,
            frameworks,
            build_tool: Some("Maven".to_string()),
        };
    }
    if root.join("build.gradle").exists() || root.join("build.gradle.kts").exists() {
        let manifest = if root.join("build.gradle.kts").exists() {
            "build.gradle.kts"
        } else {
            "build.gradle"
        };
        let frameworks = detect_java_frameworks(root, manifest);
        return ProjectType {
            language: Language::Java,
            frameworks,
            build_tool: Some("Gradle".to_string()),
        };
    }

    // Fallback: extension frequency
    language_from_extensions(files)
}

fn detect_rust_frameworks(root: &Path) -> Vec<Framework> {
    let content = read_manifest(root, "Cargo.toml");
    let mut frameworks = Vec::new();
    if contains_dep(&content, "axum") {
        frameworks.push(Framework::Axum);
    }
    if contains_dep(&content, "actix-web") {
        frameworks.push(Framework::Actix);
    }
    if contains_dep(&content, "rocket") {
        frameworks.push(Framework::Rocket);
    }
    frameworks
}

fn detect_js_frameworks(root: &Path) -> Vec<Framework> {
    let content = read_manifest(root, "package.json");
    let mut frameworks = Vec::new();

    // Next.js must be checked before React (Next includes React)
    if contains_dep(&content, "next") {
        frameworks.push(Framework::Nextjs);
    } else if contains_dep(&content, "react") {
        frameworks.push(Framework::React);
    }
    if contains_dep(&content, "vue") {
        frameworks.push(Framework::Vue);
    }
    if contains_dep(&content, "svelte") {
        frameworks.push(Framework::Svelte);
    }
    if contains_dep(&content, "express") {
        frameworks.push(Framework::Express);
    }
    if contains_dep(&content, "@nestjs/core") {
        frameworks.push(Framework::Nestjs);
    }
    frameworks
}

fn detect_js_build_tool(root: &Path) -> String {
    if root.join("bun.lockb").exists() || root.join("bun.lock").exists() {
        "bun".to_string()
    } else if root.join("pnpm-lock.yaml").exists() {
        "pnpm".to_string()
    } else if root.join("yarn.lock").exists() {
        "yarn".to_string()
    } else {
        "npm".to_string()
    }
}

fn detect_python_frameworks(root: &Path) -> Vec<Framework> {
    // Check pyproject.toml first, then requirements.txt
    let content = if root.join("pyproject.toml").exists() {
        read_manifest(root, "pyproject.toml")
    } else if root.join("requirements.txt").exists() {
        read_manifest(root, "requirements.txt")
    } else {
        String::new()
    };

    let mut frameworks = Vec::new();
    if contains_dep(&content, "django") || contains_dep(&content, "Django") {
        frameworks.push(Framework::Django);
    }
    if contains_dep(&content, "flask") || contains_dep(&content, "Flask") {
        frameworks.push(Framework::Flask);
    }
    if contains_dep(&content, "fastapi") || contains_dep(&content, "FastAPI") {
        frameworks.push(Framework::FastApi);
    }
    frameworks
}

fn detect_python_build_tool(root: &Path) -> String {
    let content = read_manifest(root, "pyproject.toml");
    if content.contains("[tool.poetry]") {
        "poetry".to_string()
    } else if content.contains("hatchling") || content.contains("[tool.hatch]") {
        "hatch".to_string()
    } else if content.contains("[tool.pdm]") {
        "pdm".to_string()
    } else if content.contains("uv") && content.contains("[tool.uv]") {
        "uv".to_string()
    } else {
        "pip".to_string()
    }
}

fn detect_go_frameworks(root: &Path) -> Vec<Framework> {
    let content = read_manifest(root, "go.mod");
    let mut frameworks = Vec::new();
    if content.contains("github.com/gin-gonic/gin") {
        frameworks.push(Framework::Gin);
    }
    if content.contains("github.com/labstack/echo") {
        frameworks.push(Framework::Echo);
    }
    frameworks
}

fn detect_java_frameworks(root: &Path, manifest: &str) -> Vec<Framework> {
    let content = read_manifest(root, manifest);
    let mut frameworks = Vec::new();
    if content.contains("spring") || content.contains("Spring") {
        frameworks.push(Framework::Spring);
    }
    frameworks
}

fn read_manifest(root: &Path, name: &str) -> String {
    std::fs::read_to_string(root.join(name)).unwrap_or_default()
}

/// Simple dependency check: looks for the dep name as a substring.
/// Works for TOML tables (`axum = `) and JSON (`"express":`).
fn contains_dep(content: &str, dep: &str) -> bool {
    content.contains(dep)
}

/// Fallback: count file extensions and pick the most common language.
fn language_from_extensions(files: &[std::path::PathBuf]) -> ProjectType {
    let mut counts: HashMap<&str, usize> = HashMap::new();
    for file in files {
        if let Some(ext) = file.extension().and_then(|e| e.to_str()) {
            let lang = match ext {
                "rs" => "rust",
                "ts" | "tsx" => "typescript",
                "js" | "jsx" | "mjs" | "cjs" => "javascript",
                "py" | "pyi" => "python",
                "go" => "go",
                "java" => "java",
                _ => continue,
            };
            *counts.entry(lang).or_default() += 1;
        }
    }

    let winner = counts
        .into_iter()
        .max_by_key(|(_, count)| *count)
        .map(|(lang, _)| lang);

    match winner {
        Some("rust") => ProjectType {
            language: Language::Rust,
            frameworks: Vec::new(),
            build_tool: None,
        },
        Some("typescript") => ProjectType {
            language: Language::TypeScript,
            frameworks: Vec::new(),
            build_tool: None,
        },
        Some("javascript") => ProjectType {
            language: Language::JavaScript,
            frameworks: Vec::new(),
            build_tool: None,
        },
        Some("python") => ProjectType {
            language: Language::Python,
            frameworks: Vec::new(),
            build_tool: None,
        },
        Some("go") => ProjectType {
            language: Language::Go,
            frameworks: Vec::new(),
            build_tool: None,
        },
        Some("java") => ProjectType {
            language: Language::Java,
            frameworks: Vec::new(),
            build_tool: None,
        },
        _ => ProjectType::unknown(),
    }
}

#[cfg(test)]
#[expect(clippy::unwrap_used, reason = "test code")]
mod tests {
    use super::*;
    use std::path::PathBuf;

    #[test]
    fn detect_rust_project() {
        let dir = tempfile::tempdir().unwrap();
        std::fs::write(
            dir.path().join("Cargo.toml"),
            "[package]\nname = \"test\"\n\n[dependencies]\naxum = \"0.7\"\n",
        )
        .unwrap();

        let pt = detect_project_type(dir.path(), &[]);
        assert_eq!(pt.language, Language::Rust);
        assert_eq!(pt.build_tool.as_deref(), Some("Cargo"));
        assert!(pt.frameworks.contains(&Framework::Axum));
    }

    #[test]
    fn detect_typescript_project() {
        let dir = tempfile::tempdir().unwrap();
        std::fs::write(
            dir.path().join("package.json"),
            r#"{"dependencies":{"next":"14","react":"18"}}"#,
        )
        .unwrap();
        std::fs::write(dir.path().join("tsconfig.json"), "{}").unwrap();
        std::fs::write(dir.path().join("pnpm-lock.yaml"), "").unwrap();

        let pt = detect_project_type(dir.path(), &[]);
        assert_eq!(pt.language, Language::TypeScript);
        assert_eq!(pt.build_tool.as_deref(), Some("pnpm"));
        assert!(pt.frameworks.contains(&Framework::Nextjs));
        // Next.js suppresses standalone React
        assert!(!pt.frameworks.contains(&Framework::React));
    }

    #[test]
    fn detect_javascript_without_tsconfig() {
        let dir = tempfile::tempdir().unwrap();
        std::fs::write(
            dir.path().join("package.json"),
            r#"{"dependencies":{"express":"4"}}"#,
        )
        .unwrap();

        let pt = detect_project_type(dir.path(), &[]);
        assert_eq!(pt.language, Language::JavaScript);
        assert!(pt.frameworks.contains(&Framework::Express));
    }

    #[test]
    fn detect_python_project() {
        let dir = tempfile::tempdir().unwrap();
        std::fs::write(
            dir.path().join("pyproject.toml"),
            "[tool.poetry]\nname = \"test\"\n\n[tool.poetry.dependencies]\nfastapi = \"*\"\n",
        )
        .unwrap();

        let pt = detect_project_type(dir.path(), &[]);
        assert_eq!(pt.language, Language::Python);
        assert_eq!(pt.build_tool.as_deref(), Some("poetry"));
        assert!(pt.frameworks.contains(&Framework::FastApi));
    }

    #[test]
    fn detect_go_project() {
        let dir = tempfile::tempdir().unwrap();
        std::fs::write(
            dir.path().join("go.mod"),
            "module test\n\nrequire github.com/gin-gonic/gin v1.9\n",
        )
        .unwrap();

        let pt = detect_project_type(dir.path(), &[]);
        assert_eq!(pt.language, Language::Go);
        assert!(pt.frameworks.contains(&Framework::Gin));
    }

    #[test]
    fn detect_java_maven() {
        let dir = tempfile::tempdir().unwrap();
        std::fs::write(
            dir.path().join("pom.xml"),
            "<project><dependencies><dependency>spring-boot</dependency></dependencies></project>",
        )
        .unwrap();

        let pt = detect_project_type(dir.path(), &[]);
        assert_eq!(pt.language, Language::Java);
        assert_eq!(pt.build_tool.as_deref(), Some("Maven"));
        assert!(pt.frameworks.contains(&Framework::Spring));
    }

    #[test]
    fn fallback_to_extension_counting() {
        let dir = tempfile::tempdir().unwrap();
        let files = vec![
            PathBuf::from("src/main.py"),
            PathBuf::from("src/utils.py"),
            PathBuf::from("src/models.py"),
            PathBuf::from("README.md"),
        ];

        let pt = detect_project_type(dir.path(), &files);
        assert_eq!(pt.language, Language::Python);
        assert!(pt.frameworks.is_empty());
    }

    #[test]
    fn unknown_for_empty_project() {
        let dir = tempfile::tempdir().unwrap();
        let pt = detect_project_type(dir.path(), &[]);
        assert_eq!(pt.language, Language::Unknown);
    }
}
