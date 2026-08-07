"""Map file paths to languages the way GitHub Linguist roughly does.

Attribution works off commit diffs, so every changed file has to be resolved to a
language by its path alone. This module also filters out the paths that would
otherwise dominate a diff-based count: vendored dependencies, build output,
lockfiles and minified bundles.
"""

import posixpath
import re
from typing import Dict, List, Optional, Set

# Extension -> language. Keys are lowercase and include the leading dot.
EXTENSION_LANGUAGES: Dict[str, str] = {
    ".c": "C",
    ".h": "C",
    ".cc": "C++",
    ".cpp": "C++",
    ".cxx": "C++",
    ".c++": "C++",
    ".hpp": "C++",
    ".hh": "C++",
    ".hxx": "C++",
    ".cs": "C#",
    ".csx": "C#",
    ".m": "Objective-C",
    ".mm": "Objective-C++",
    ".swift": "Swift",
    ".java": "Java",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".scala": "Scala",
    ".sc": "Scala",
    ".groovy": "Groovy",
    ".gradle": "Gradle",
    ".clj": "Clojure",
    ".cljs": "ClojureScript",
    ".cljc": "Clojure",
    ".go": "Go",
    ".rs": "Rust",
    ".zig": "Zig",
    ".nim": "Nim",
    ".d": "D",
    ".dart": "Dart",
    ".py": "Python",
    ".pyi": "Python",
    ".pyx": "Cython",
    ".pxd": "Cython",
    ".ipynb": "Jupyter Notebook",
    ".rb": "Ruby",
    ".rake": "Ruby",
    ".gemspec": "Ruby",
    ".erb": "HTML+ERB",
    ".php": "PHP",
    ".phtml": "PHP",
    ".pl": "Perl",
    ".pm": "Perl",
    ".raku": "Raku",
    ".lua": "Lua",
    ".r": "R",
    ".rmd": "R",
    ".jl": "Julia",
    ".ex": "Elixir",
    ".exs": "Elixir",
    ".erl": "Erlang",
    ".hrl": "Erlang",
    ".hs": "Haskell",
    ".lhs": "Haskell",
    ".ml": "OCaml",
    ".mli": "OCaml",
    ".fs": "F#",
    ".fsi": "F#",
    ".fsx": "F#",
    ".elm": "Elm",
    ".purs": "PureScript",
    ".cr": "Crystal",
    ".v": "V",
    ".sol": "Solidity",
    ".move": "Move",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".mts": "TypeScript",
    ".cts": "TypeScript",
    ".vue": "Vue",
    ".svelte": "Svelte",
    ".astro": "Astro",
    ".html": "HTML",
    ".htm": "HTML",
    ".xhtml": "HTML",
    ".ejs": "EJS",
    ".hbs": "Handlebars",
    ".handlebars": "Handlebars",
    ".mustache": "Mustache",
    ".pug": "Pug",
    ".jade": "Pug",
    ".haml": "Haml",
    ".twig": "Twig",
    ".liquid": "Liquid",
    ".css": "CSS",
    ".scss": "SCSS",
    ".sass": "Sass",
    ".less": "Less",
    ".styl": "Stylus",
    ".sh": "Shell",
    ".bash": "Shell",
    ".zsh": "Shell",
    ".fish": "Shell",
    ".ps1": "PowerShell",
    ".psm1": "PowerShell",
    ".psd1": "PowerShell",
    ".bat": "Batchfile",
    ".cmd": "Batchfile",
    ".sql": "SQL",
    ".psql": "SQL",
    ".plsql": "PLSQL",
    ".prisma": "Prisma",
    ".graphql": "GraphQL",
    ".gql": "GraphQL",
    ".proto": "Protocol Buffer",
    ".thrift": "Thrift",
    ".tf": "HCL",
    ".tfvars": "HCL",
    ".hcl": "HCL",
    ".nix": "Nix",
    ".dockerfile": "Dockerfile",
    ".vim": "Vim Script",
    ".el": "Emacs Lisp",
    ".lisp": "Common Lisp",
    ".scm": "Scheme",
    ".rkt": "Racket",
    ".ada": "Ada",
    ".adb": "Ada",
    ".f": "Fortran",
    ".f90": "Fortran",
    ".f95": "Fortran",
    ".for": "Fortran",
    ".pas": "Pascal",
    ".pp": "Pascal",
    ".asm": "Assembly",
    ".s": "Assembly",
    ".wat": "WebAssembly",
    ".wgsl": "WGSL",
    ".glsl": "GLSL",
    ".vert": "GLSL",
    ".frag": "GLSL",
    ".hlsl": "HLSL",
    ".metal": "Metal",
    ".cu": "Cuda",
    ".cuh": "Cuda",
    ".sv": "SystemVerilog",
    ".vhd": "VHDL",
    ".vhdl": "VHDL",
    ".tex": "TeX",
    ".bib": "BibTeX",
    ".md": "Markdown",
    ".markdown": "Markdown",
    ".mdx": "MDX",
    ".rst": "reStructuredText",
    ".adoc": "AsciiDoc",
    ".org": "Org",
    ".txt": "Text",
    ".json": "JSON",
    ".jsonc": "JSON",
    ".json5": "JSON5",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".toml": "TOML",
    ".ini": "INI",
    ".cfg": "INI",
    ".conf": "INI",
    ".xml": "XML",
    ".xsl": "XML",
    ".xsd": "XML",
    ".plist": "XML",
    ".csv": "CSV",
    ".tsv": "TSV",
    ".env": "Dotenv",
    ".makefile": "Makefile",
    ".mk": "Makefile",
    ".cmake": "CMake",
    ".bzl": "Starlark",
    ".just": "Just",
    ".applescript": "AppleScript",
    ".ahk": "AutoHotkey",
    ".gd": "GDScript",
    ".sml": "Standard ML",
    ".vb": "Visual Basic",
    ".vbs": "VBScript",
    ".m4": "M4",
    ".awk": "Awk",
    ".sed": "sed",
}

# Exact filenames (lowercased) that map to a language regardless of extension.
FILENAME_LANGUAGES: Dict[str, str] = {
    "dockerfile": "Dockerfile",
    "containerfile": "Dockerfile",
    "makefile": "Makefile",
    "gnumakefile": "Makefile",
    "cmakelists.txt": "CMake",
    "rakefile": "Ruby",
    "gemfile": "Ruby",
    "podfile": "Ruby",
    "fastfile": "Ruby",
    "brewfile": "Ruby",
    "vagrantfile": "Ruby",
    "justfile": "Just",
    "procfile": "Procfile",
    "jenkinsfile": "Groovy",
    "build": "Starlark",
    "workspace": "Starlark",
    ".gitignore": "Ignore List",
    ".gitattributes": "Git Attributes",
    ".editorconfig": "EditorConfig",
    ".env": "Dotenv",
    "license": "Text",
    "readme": "Markdown",
    "codeowners": "CODEOWNERS",
}

# Lockfiles and other generated manifests: authored by a tool, not by a person.
GENERATED_FILENAMES: Set[str] = {
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "bun.lock",
    "bun.lockb",
    "npm-shrinkwrap.json",
    "composer.lock",
    "gemfile.lock",
    "podfile.lock",
    "cargo.lock",
    "poetry.lock",
    "pdm.lock",
    "uv.lock",
    "pipfile.lock",
    "go.sum",
    "flake.lock",
    "packages.lock.json",
    "mix.lock",
    "pubspec.lock",
    "gradle.lockfile",
}

# Path segments that mean "not written here" (vendored deps or build output).
VENDORED_SEGMENTS: Set[str] = {
    "node_modules",
    "bower_components",
    "jspm_packages",
    "vendor",
    "vendors",
    "third_party",
    "thirdparty",
    "external",
    "dist",
    "build",
    "out",
    "target",
    "bin",
    "obj",
    "coverage",
    "__pycache__",
    "site-packages",
    ".venv",
    "venv",
    "env",
    ".next",
    ".nuxt",
    ".svelte-kit",
    ".output",
    ".turbo",
    ".parcel-cache",
    ".gradle",
    ".terraform",
    "pods",
    "carthage",
    "migrations",
    "generated",
    "gen",
    "__generated__",
    "public/assets",
    "staticfiles",
}

GENERATED_PATTERNS = [
    re.compile(r"\.min\.(js|css)$"),
    re.compile(r"\.bundle\.(js|css)$"),
    re.compile(r"[.-]lock\.(json|ya?ml)$"),
    re.compile(r"\.pb\.(go|py|cc|h)$"),
    re.compile(r"_pb2(_grpc)?\.pyi?$"),
    re.compile(r"\.g\.dart$"),
    re.compile(r"\.freezed\.dart$"),
    re.compile(r"\.generated\.[a-z0-9]+$"),
    re.compile(r"\.designer\.cs$"),
    re.compile(r"\.d\.ts$"),
    re.compile(r"(^|/)swagger\.(json|ya?ml)$"),
]

# Documentation, config and data formats. Kept separate from prose-vs-code so
# callers can drop them without hardcoding a list.
NON_CODE_LANGUAGES: Set[str] = {
    "Markdown",
    "MDX",
    "Text",
    "reStructuredText",
    "AsciiDoc",
    "Org",
    "JSON",
    "JSON5",
    "YAML",
    "TOML",
    "INI",
    "XML",
    "CSV",
    "TSV",
    "Dotenv",
    "Ignore List",
    "Git Attributes",
    "EditorConfig",
    "CODEOWNERS",
    "BibTeX",
    "SVG",
}


def is_vendored(path: str) -> bool:
    """True when the path lives in vendored, generated or build-output territory."""
    normalized = path.replace("\\", "/").lower()
    parts = normalized.split("/")

    if any(part in VENDORED_SEGMENTS for part in parts[:-1]):
        return True

    filename = parts[-1]
    if filename in GENERATED_FILENAMES:
        return True

    return any(pattern.search(normalized) for pattern in GENERATED_PATTERNS)


def detect_language(path: str) -> Optional[str]:
    """Resolve a repo-relative file path to a language name, or ``None``."""
    if not path:
        return None

    normalized = path.replace("\\", "/")
    filename = posixpath.basename(normalized).lower()
    if not filename:
        return None

    if filename in FILENAME_LANGUAGES:
        return FILENAME_LANGUAGES[filename]

    # "Dockerfile.dev", "makefile.common", "readme.old" and friends.
    stem = filename.split(".", 1)[0]
    if stem in FILENAME_LANGUAGES and stem in {"dockerfile", "makefile", "jenkinsfile"}:
        return FILENAME_LANGUAGES[stem]

    _, extension = posixpath.splitext(filename)
    if not extension:
        return None

    return EXTENSION_LANGUAGES.get(extension.lower())


def filter_languages(
    totals: Dict[str, int], excluded: Optional[List[str]] = None
) -> Dict[str, int]:
    """Drop excluded languages, matching case-insensitively."""
    if not excluded:
        return dict(totals)

    excluded_set = {name.strip().lower() for name in excluded if name and name.strip()}
    return {
        name: value
        for name, value in totals.items()
        if name.lower() not in excluded_set
    }
