# Claude Code Guide for DocuMark

This file provides instructions for Claude Code when working on the DocuMark project.

## Project Overview

DocuMark is a Python tool that converts binary documents (PDFs, Word docs, images) to Markdown using AI. It uses Gemini 2.5 Flash via LiteLLM for document understanding and provides both CLI and programmatic interfaces.

## Key Design Decisions

1. **Focus on Binary Files**: We only process files that Claude Code cannot read natively (PDFs, images, Word docs, Google Docs)
2. **Direct LiteLLM Usage**: Use LiteLLM directly without wrapper abstractions
3. **Async Processing**: Support concurrent processing for batch/recursive conversions
4. **Pattern-Based Output**: Flexible output paths using variables like `{filename}`, `{timestamp}`
5. **Change Detection**: Track conversions with metadata to skip unchanged files
6. **JSON Schema Output**: Use structured output to ensure clean Markdown extraction

## Code Style

- Use Python 3.9+ type hints with built-in types (`list`, `dict`) not typing module
- Follow existing code patterns in the codebase
- Keep functions focused and modular
- Add docstrings to all public functions and classes
- Use ruff and mypy for linting (pre-commit hooks are configured)

## Testing

Before committing changes:
1. Run: `ruff check src/ --fix --unsafe-fixes`
2. Run: `mypy src/`
3. Test the CLI with sample documents

## Common Commands

- Install: `pip install -e .`
- Convert a file: `documark convert document.pdf`
- Recursive conversion: `documark convert . --recursive --pattern ".{filename}.md"`
- Check status: `documark status .`

## Architecture

```
src/documark/
├── processors/           # Document processors
│   ├── base.py          # Abstract base classes
│   ├── file/            # Local file processors
│   │   ├── pdf.py       # PDF processor using PyMuPDF
│   │   ├── docx.py      # Word processor (converts to PDF)
│   │   └── image.py     # Direct image processor
│   └── cloud/           # Cloud file processors
│       └── google_docs.py # Google Docs processor
├── core/                # Core conversion logic
│   ├── converter.py     # Main converter with LLM integration
│   ├── async_converter.py # Async wrapper for concurrency
│   ├── metadata.py      # Change tracking
│   └── patterns.py      # Output path patterns
├── cli/                 # CLI interface
│   └── main.py          # Typer commands
└── utils/               # Utility functions
    └── image_utils.py   # Image encoding/optimization
```

## Adding New Features

When adding new document types:
1. Create a new processor in `processors/file/` or `processors/cloud/`
2. Inherit from `ImageBasedProcessor` or `TextBasedProcessor`
3. Implement required methods: `supported_extensions`, `process`
4. Add the processor to the converter's processor list

## Environment Variables

- `GEMINI_API_KEY`: Required for Gemini models
- `OPENAI_API_KEY`: Optional for OpenAI models
- `ANTHROPIC_API_KEY`: Optional for Anthropic models

## Dependencies

Core dependencies:
- `litellm`: LLM provider abstraction
- `PyMuPDF`: PDF rendering (imported as `fitz`)
- `typer`: CLI framework
- `rich`: Terminal formatting
- `Pillow`: Image processing
- `python-docx`: Word document reading
- `docx2pdf`: Word to PDF conversion
