# How to Use the Code for Images or PDF Files

You can use the application to process both images and PDF files. Here's a step-by-step guide:

## Prerequisites

Before you start, make sure you have:

1. **Installed Ollama**: Download from [Ollama's website](https://ollama.ai/)
2. **Pulled a vision model**: Run `ollama pull granite3.2-vision:latest` or `ollama pull llava`
3. **Installed dependencies**: Run `pip install -r requirements.txt`
4. **For PDF processing**: Install Poppler
   - macOS: `brew install poppler`
   - Ubuntu/Debian: `apt-get install poppler-utils`
   - Windows: Follow instructions at [pdf2image documentation](https://pdf2image.readthedocs.io/en/latest/installation.html)

## Processing a Single Image

To process a single image file:

```bash
python src/files2knowledge.py --input_path /path/to/your/image.jpg --output_dir /path/to/output
```

python src/files2knowledge.py --input_path ./input/openai/openai_one_page.jpeg --output_dir ./output/openai

This will:
1. Load the image
2. Send it to the Ollama vision model
3. Generate a description
4. Save the result as a JSON file in your output directory

The output JSON will look like:
```json
{
  "filename": "image.jpg",
  "timestamp": "20240615_123045",
  "description": "Detailed description of the image content..."
}
```

## Processing a PDF File

To process a PDF file:

```bash
python src/files2knowledge.py --input_path /path/to/your/document.pdf --output_dir /path/to/output
```

This will:
1. Convert the PDF to individual page images
2. Process each page with the vision model
3. Create a dedicated folder in your output directory named `document_TIMESTAMP`
4. Save individual JSON files for each page
5. Create a combined JSON file with all page descriptions

The combined JSON will look like:
```json
{
  "filename": "document.pdf",
  "timestamp": "20240615_123045",
  "total_pages": 5,
  "pages": {
    "1": "Description of page 1...",
    "2": "Description of page 2...",
    "3": "Description of page 3..."
  }
}
```

## Processing a Directory

To process all images and PDFs in a directory:

```bash
python src/files2knowledge.py --input_path /path/to/directory --output_dir /path/to/output
```

This will find and process all supported files (images and PDFs) in the directory.

## Advanced Options

### Using a Different Model

```bash
python src/files2knowledge.py --input_path /path/to/image.jpg --output_dir /path/to/output --model bakllava
```

### Custom Prompt

```bash
python src/files2knowledge.py --input_path /path/to/image.jpg --output_dir /path/to/output --prompt "Describe this image in detail, focusing on the text content."
```

### Remote Ollama Instance

```bash
python src/files2knowledge.py --input_path /path/to/image.jpg --output_dir /path/to/output --api_url http://remote-server:11434
```

## Example Workflow

1. **Start Ollama**: Make sure Ollama is running on your machine
2. **Prepare your files**: Gather the images or PDFs you want to process
3. **Run the command**:
   ```bash
   python src/pptx2knowledge.py --input_path ~/Documents/presentation.pdf --output_dir ~/Documents/output
   ```
4. **Check the results**: Look in your output directory for the JSON files with descriptions

Each run creates files with unique timestamps, so you can process the same files multiple times without overwriting previous results.
