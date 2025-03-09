import argparse
import logging
import sys
from pathlib import Path
import os
import requests
import json
import base64
from typing import Union, List, Optional, Dict
import tempfile
from tqdm import tqdm
from PIL import Image
import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class OllamaClient:
    """
    Client for interacting with Ollama's local API for vision-language models.
    """
    def __init__(self, model_name: str = "granite3.2-vision:latest", api_url: str = "http://localhost:11434"):
        self.model_name = model_name
        self.api_url = api_url
        self.api_endpoint = f"{api_url}/api/generate"
        
        # Check if Ollama is running and the model is available
        self._check_model_availability()
    
    def _check_model_availability(self):
        """Check if Ollama is running and the specified model is available."""
        try:
            response = requests.get(f"{self.api_url}/api/tags")
            if response.status_code != 200:
                logger.error(f"Failed to connect to Ollama API: {response.status_code}")
                raise ConnectionError(f"Failed to connect to Ollama API: {response.status_code}")
            
            models = response.json().get("models", [])
            model_names = [model.get("name") for model in models]
            
            if self.model_name not in model_names:
                logger.warning(f"Model '{self.model_name}' not found in Ollama. Available models: {', '.join(model_names)}")
                logger.warning(f"You may need to run: ollama pull {self.model_name}")
        except requests.RequestException as e:
            logger.error(f"Error connecting to Ollama: {e}")
            raise ConnectionError(f"Error connecting to Ollama: {e}")
    
    def generate(self, prompt: str, image_path: Union[str, Path]) -> str:
        """
        Generate content using the Ollama model with text + image as input.

        :param prompt: A textual prompt to provide to the model.
        :param image_path: File path (string or Path) to an image to be included in the request.
        :return: The generated response text from the model.
        """
        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f"Image file not found: {image_path}")
        
        # Open and resize image before processing
        img = Image.open(image_path)
        img = img.resize((800, 600))  # Adjust dimensions as needed
        resized_path = str(image_path) + "_resized.jpg"
        img.save(resized_path)
        
        # Encode image to base64
        with open(resized_path, "rb") as img_file:
            base64_image = base64.b64encode(img_file.read()).decode("utf-8")
        
        # Prepare the request payload
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "images": [base64_image],
            "stream": False
        }
        
        try:
            response = requests.post(self.api_endpoint, json=payload)
            response.raise_for_status()
            result = response.json()
            return result.get("response", "")
        except requests.RequestException as e:
            logger.error(f"Error calling Ollama API: {e}")
            raise Exception(f"Error calling Ollama API: {e}")

def process_image(
    image_path: Path,
    output_dir: Path,
    ollama_client: OllamaClient,
    prompt: str
) -> Path:
    """
    Process a single image file and save the description in JSON format.
    
    Args:
        image_path: Path to the image file
        output_dir: Directory to save the output
        ollama_client: Ollama client instance
        prompt: Prompt to use for the description
        
    Returns:
        Path to the output file
    """
    logger.info(f"Processing image: {image_path}")
    
    try:
        # Generate description using Ollama
        description = ollama_client.generate(prompt, image_path)
        
        # Create timestamp for unique filename
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create output file path with timestamp
        output_file = output_dir / f"{image_path.stem}_description_{timestamp}.json"
        
        # Create JSON data
        json_data = {
            "filename": image_path.name,
            "timestamp": timestamp,
            "description": description
        }
        
        # Save description to JSON file
        with open(output_file, "w") as f:
            json.dump(json_data, f, indent=2)
            
        logger.info(f"Description saved to: {output_file}")
        return output_file
    except Exception as e:
        logger.error(f"Error processing image {image_path}: {e}")
        raise

def process_pdf(
    pdf_path: Path,
    output_dir: Path,
    ollama_client: OllamaClient,
    prompt: str
) -> List[Path]:
    """
    Process a PDF file by converting it to images and then processing each image.
    Creates a folder for the PDF output and stores results in JSON format.
    
    Args:
        pdf_path: Path to the PDF file
        output_dir: Directory to save the output
        ollama_client: Ollama client instance
        prompt: Prompt to use for the description
        
    Returns:
        List of paths to the output files
    """
    logger.info(f"Processing PDF: {pdf_path}")
    
    try:
        # Create a timestamp for unique filenames
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create a specific folder for this PDF's output
        pdf_output_dir = output_dir / f"{pdf_path.stem}_{timestamp}"
        pdf_output_dir.mkdir(parents=True, exist_ok=True)
        
        # Create a temporary directory for the images
        with tempfile.TemporaryDirectory() as temp_dir_str:
            temp_dir = Path(temp_dir_str)
            
            # Convert PDF to images using pdf2image
            try:
                from pdf2image import convert_from_path
                images = convert_from_path(pdf_path)
            except ImportError:
                logger.error("pdf2image not installed. Install it with: pip install pdf2image")
                logger.error("You may also need to install poppler: https://pdf2image.readthedocs.io/en/latest/installation.html")
                raise
            
            # Save images to temporary directory
            image_paths = []
            for i, image in enumerate(images):
                image_path = temp_dir / f"page_{i+1}.png"
                image.save(image_path)
                image_paths.append(image_path)
            
            # Process each image
            output_files = []
            descriptions = {}
            
            for i, image_path in enumerate(tqdm(image_paths, desc="Processing PDF pages")):
                page_num = i + 1
                output_file = pdf_output_dir / f"page_{page_num}_description.json"
                
                # Generate description
                description = ollama_client.generate(prompt, image_path)
                
                # Store in descriptions dictionary
                descriptions[str(page_num)] = description
                
                # Save individual page description as JSON
                page_json = {
                    "page": page_num,
                    "filename": pdf_path.name,
                    "timestamp": timestamp,
                    "description": description
                }
                
                with open(output_file, "w") as f:
                    json.dump(page_json, f, indent=2)
                
                output_files.append(output_file)
            
            # Create a combined JSON file with all descriptions
            combined_output = pdf_output_dir / f"{pdf_path.stem}_all_descriptions.json"
            
            combined_json = {
                "filename": pdf_path.name,
                "timestamp": timestamp,
                "total_pages": len(images),
                "pages": descriptions
            }
            
            with open(combined_output, "w") as f:
                json.dump(combined_json, f, indent=2)
            
            logger.info(f"Combined descriptions saved to: {combined_output}")
            output_files.append(combined_output)
            
            return output_files
    except Exception as e:
        logger.error(f"Error processing PDF {pdf_path}: {e}")
        raise

def process_input_path(
    input_path: Path,
    output_dir: Path,
    ollama_client: OllamaClient,
    prompt: str
) -> List[Path]:
    """
    Process an input path (file or directory) and generate descriptions.
    
    Args:
        input_path: Path to the input file or directory
        output_dir: Directory to save the output
        ollama_client: Ollama client instance
        prompt: Prompt to use for the description
        
    Returns:
        List of paths to the output files
    """
    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_files = []
    
    if input_path.is_file():
        # Process a single file
        if input_path.suffix.lower() in ['.pdf']:
            logger.info(f"Processing PDF file: {input_path}")
            output_files.extend(process_pdf(input_path, output_dir, ollama_client, prompt))
        elif input_path.suffix.lower() in ['.jpg', '.jpeg', '.png', '.bmp', '.gif']:
            logger.info(f"Processing image file: {input_path}")
            output_files.append(process_image(input_path, output_dir, ollama_client, prompt))
        else:
            logger.warning(f"Unsupported file type: {input_path}")
    elif input_path.is_dir():
        # Process all files in the directory
        logger.info(f"Processing directory: {input_path}")
        
        # Find all supported files
        pdf_files = list(input_path.glob('**/*.pdf'))
        image_files = []
        for ext in ['.jpg', '.jpeg', '.png', '.bmp', '.gif']:
            image_files.extend(list(input_path.glob(f'**/*{ext}')))
        
        # Process PDFs
        if pdf_files:
            logger.info(f"Found {len(pdf_files)} PDF files")
            for pdf_file in pdf_files:
                output_files.extend(process_pdf(pdf_file, output_dir, ollama_client, prompt))
        
        # Process images
        if image_files:
            logger.info(f"Found {len(image_files)} image files")
            for image_file in image_files:
                output_files.append(process_image(image_file, output_dir, ollama_client, prompt))
    else:
        logger.error(f"Input path does not exist: {input_path}")
        raise FileNotFoundError(f"Input path does not exist: {input_path}")
    
    return output_files

def parse_args(input_args=None):
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Convert images and PDFs to semantic descriptions using Ollama.")
    
    parser.add_argument(
        "--input_path",
        type=str,
        required=True,
        help="Path to input file or directory"
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        required=True,
        help="Output directory path"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="granite3.2-vision:latest",
        help="Ollama model to use (default: granite3.2-vision:latest)"
    )
    parser.add_argument(
        "--api_url",
        type=str,
        default="http://localhost:11434",
        help="Ollama API URL (default: http://localhost:11434)"
    )
    parser.add_argument(
        "--prompt",
        type=str,
        default="""
            You are an expert AI assistant tasked with converting PowerPoint slides into semantically rich text for downstream use. 
            Carefully observe the content of each slide and accurately transcribe all text present. 
            Provide detailed descriptions of any graphs, charts, figures, or other visual elements. 
            It is essential to ensure accuracy and completeness in your text-based representation of the slide. 
            Where possible, include interpretations of graphics, icons, and other non-text descriptors.
            If there is no text, just describe the image.

            Return only the text content of the slide, without any preamble, explanation, or unrelated information.
        """,
        help="Prompt to use for the description"
    )
    
    if input_args is not None:
        return parser.parse_args(input_args)
    return parser.parse_args()

def main():
    """Main entry point for the application."""
    args = parse_args()
    
    input_path = Path(args.input_path)
    output_dir = Path(args.output_dir)
    
    # Create Ollama client
    ollama_client = OllamaClient(model_name=args.model, api_url=args.api_url)
    
    try:
        # Process input path
        output_files = process_input_path(input_path, output_dir, ollama_client, args.prompt)
        
        # Print summary
        pdf_outputs = [f for f in output_files if "_all_descriptions.json" in str(f)]
        image_outputs = [f for f in output_files if "_description_" in str(f) and f not in pdf_outputs]
        
        logger.info(f"Processing complete.")
        logger.info(f"Generated {len(image_outputs)} image description files.")
        logger.info(f"Generated {len(pdf_outputs)} PDF description files.")
        logger.info(f"Output directory: {output_dir}")
        
        # Print example of how to access the JSON data
        if output_files:
            logger.info("JSON output format example:")
            logger.info("  - For single images: {'filename': 'image.jpg', 'timestamp': '20240615_123045', 'description': '...'}")
            logger.info("  - For PDFs: {'filename': 'document.pdf', 'timestamp': '20240615_123045', 'total_pages': 5, 'pages': {'1': '...', '2': '...', ...}}")
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
