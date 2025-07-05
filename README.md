# DocuMark

Convert documents to markdown using AI. DocuMark takes your PDFs, Word documents, and images and converts them to clean, well-formatted Markdown using Gemini 2.5 Flash or other LLMs.

## Features

- 📄 **Multiple Format Support**: PDF, DOCX, DOC, and common image formats
- 🚀 **Fast Processing**: Uses PyMuPDF for efficient document rendering
- 🤖 **AI-Powered**: Leverages Gemini 2.5 Flash for accurate text extraction
- 🔄 **Batch Processing**: Convert multiple documents at once
- 🎨 **Beautiful CLI**: Rich terminal interface with progress indicators
- 🔌 **Extensible**: Easy to add support for other LLM providers via LiteLLM

## Installation

```bash
pip install -e .
```

## Quick Start

1. Set up your API key:
```bash
export GEMINI_API_KEY=your_gemini_api_key_here
```

2. Convert a document:
```bash
documark convert document.pdf
```

## Usage

### Convert a single document
```bash
documark convert document.pdf --output output.md
```

### Convert multiple documents
```bash
documark convert *.pdf --output converted/
```

### Use a different model
```bash
documark convert document.pdf --model gpt-4o
```

### Custom DPI for rendering
```bash
documark convert document.pdf --dpi 150
```

### Custom conversion prompt
```bash
documark convert document.pdf --prompt "Extract only the tables from this document"
```

## CLI Commands

- `documark convert` - Convert documents to markdown
- `documark list-models` - Show available LiteLLM model strings
- `documark supported` - Show supported file types
- `documark --version` - Show version

## Python API

```python
from documark.converter import DocumentConverter

# Initialize converter
converter = DocumentConverter(model="gemini/gemini-2.5-flash")

# Convert single document
markdown = converter.convert("document.pdf", "output.md")

# Batch convert
results = converter.batch_convert(["doc1.pdf", "doc2.docx"], output_dir="converted/")
```

## Supported File Types

**Documents:**
- PDF (.pdf)
- Microsoft Word (.docx, .doc)

**Images:**
- PNG (.png)
- JPEG (.jpg, .jpeg)
- GIF (.gif)
- BMP (.bmp)
- TIFF (.tiff, .tif)
- WebP (.webp)

## Configuration

Create a `.env` file in your project root:

```env
# Required for Gemini
GEMINI_API_KEY=your_gemini_api_key_here

# Optional: Alternative providers
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

## Requirements

- Python 3.8+
- For Word document conversion on Windows: Microsoft Word installed
- For Word document conversion on macOS/Linux: LibreOffice (optional fallback)

## License

MIT
