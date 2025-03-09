import streamlit as st
import os
import tempfile
from pathlib import Path
import sys
import time
import json
from PIL import Image
from src.files2knowledge import OllamaClient, process_input_path

# Try to import pdf2image for PDF preview
try:
    from pdf2image import convert_from_path
    PDF_PREVIEW_AVAILABLE = True
except ImportError:
    PDF_PREVIEW_AVAILABLE = False

# Set page configuration
st.set_page_config(
    page_title="Files2Knowledge",
    page_icon="📄",
    layout="wide"
)

# App title and description
st.title("Files2Knowledge")
st.markdown("""
This app converts images and PDFs to semantic descriptions using Ollama's vision models.
Upload your files and get AI-generated descriptions of their content.
""")

# Sidebar for configuration
st.sidebar.header("Configuration")

# Model selection
model_name = st.sidebar.text_input(
    "Ollama Model",
    value="granite3.2-vision:latest",
    help="The Ollama vision model to use for generating descriptions"
)

# API URL
api_url = st.sidebar.text_input(
    "Ollama API URL",
    value="http://localhost:11434",
    help="The URL of your Ollama API"
)

# Custom prompt
default_prompt = """
You are an expert AI assistant tasked with converting PowerPoint slides into semantically rich text for downstream use. 
Carefully observe the content of each slide and accurately transcribe all text present. 
Provide detailed descriptions of any graphs, charts, figures, or other visual elements. 
It is essential to ensure accuracy and completeness in your text-based representation of the slide. 
Where possible, include interpretations of graphics, icons, and other non-text descriptors.
If there is no text, just describe the image.

Return only the text content of the slide, without any preamble, explanation, or unrelated information.
"""

prompt = st.sidebar.text_area(
    "Custom Prompt",
    value=default_prompt,
    height=300,
    help="The prompt to use for generating descriptions"
)

# Output directory selection
default_output_dir = os.path.join(os.getcwd(), "output")
output_dir = st.sidebar.text_input(
    "Output Directory",
    value=default_output_dir,
    help="Directory where the results will be saved"
)

# Create output directory if it doesn't exist
if not os.path.exists(output_dir):
    try:
        os.makedirs(output_dir)
        st.sidebar.success(f"Created output directory: {output_dir}")
    except Exception as e:
        st.sidebar.error(f"Error creating output directory: {e}")

# Main content area
st.header("Upload Files")

# File uploader
uploaded_files = st.file_uploader(
    "Upload images or PDFs",
    type=["jpg", "jpeg", "png", "gif", "bmp", "pdf"],
    accept_multiple_files=True,
    help="Select one or more files to process"
)

# Process button
if uploaded_files and st.button("Process Files", type="primary"):
    # Check if Ollama is available
    try:
        ollama_client = OllamaClient(model_name=model_name, api_url=api_url)
        
        # Create a progress bar
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Create a temporary directory for uploaded files
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir_path = Path(temp_dir)
            
            # Save uploaded files to temporary directory
            temp_file_paths = []
            for i, uploaded_file in enumerate(uploaded_files):
                # Update progress
                progress = (i / len(uploaded_files)) * 0.2  # First 20% for file saving
                progress_bar.progress(progress)
                status_text.text(f"Saving file: {uploaded_file.name}")
                
                # Save the file
                temp_file_path = temp_dir_path / uploaded_file.name
                with open(temp_file_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                temp_file_paths.append(temp_file_path)
            
            # Process each file
            all_output_files = []
            for i, file_path in enumerate(temp_file_paths):
                # Update progress
                start_progress = 0.2 + (i / len(temp_file_paths)) * 0.8
                end_progress = 0.2 + ((i + 1) / len(temp_file_paths)) * 0.8
                status_text.text(f"Processing file: {file_path.name}")
                
                # Process the file
                output_files = process_input_path(
                    file_path,
                    Path(output_dir),
                    ollama_client,
                    prompt
                )
                all_output_files.extend(output_files)
                
                # Update progress
                progress_bar.progress(end_progress)
            
            # Complete
            progress_bar.progress(1.0)
            status_text.text("Processing complete!")
            
            # Display results
            st.success(f"Successfully processed {len(uploaded_files)} files!")
            
            # Count PDF and image outputs
            pdf_outputs = [f for f in all_output_files if "_all_descriptions.json" in str(f)]
            image_outputs = [f for f in all_output_files if "_description_" in str(f) and f not in pdf_outputs]
            
            st.write(f"Generated {len(image_outputs)} image description files.")
            st.write(f"Generated {len(pdf_outputs)} PDF description files.")
            st.write(f"Output directory: {output_dir}")
            
            # Display side-by-side comparison for each file
            st.subheader("Results Preview")
            
            # Process each original file and its corresponding output
            for file_path in temp_file_paths:
                file_extension = file_path.suffix.lower()
                
                # Display file name as a header
                st.markdown(f"### {file_path.name}")
                
                if file_extension in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']:
                    # Find the corresponding output file
                    output_file = None
                    for out_file in image_outputs:
                        if file_path.stem in str(out_file):
                            output_file = out_file
                            break
                    
                    if output_file:
                        # Create two columns for side-by-side display
                        col1, col2 = st.columns(2)
                        
                        # Display the original image in the first column
                        with col1:
                            st.subheader("Original Image")
                            img = Image.open(file_path)
                            st.image(img, use_container_width=True)
                        
                        # Display the extracted information in the second column
                        with col2:
                            st.subheader("Extracted Information")
                            with open(output_file, 'r') as f:
                                data = json.load(f)
                                st.markdown(f"**Description:**")
                                st.markdown(data.get('description', 'No description available'))
                
                elif file_extension == '.pdf':
                    # Find the corresponding output file
                    output_file = None
                    for out_file in pdf_outputs:
                        if file_path.stem in str(out_file) and "_all_descriptions.json" in str(out_file):
                            output_file = out_file
                            break
                    
                    if output_file and PDF_PREVIEW_AVAILABLE:
                        # Load the JSON data
                        with open(output_file, 'r') as f:
                            data = json.load(f)
                        
                        # Get the total number of pages
                        total_pages = data.get('total_pages', 0)
                        pages_to_show = min(3, total_pages)  # Show max 3 pages
                        
                        st.markdown(f"**Showing {pages_to_show} of {total_pages} pages**")
                        
                        # Convert PDF to images for preview
                        pdf_images = convert_from_path(file_path, first_page=1, last_page=pages_to_show)
                        
                        # Display each page with its description
                        for i, img in enumerate(pdf_images):
                            page_num = i + 1
                            st.markdown(f"#### Page {page_num}")
                            
                            # Create two columns for side-by-side display
                            col1, col2 = st.columns(2)
                            
                            # Display the PDF page image in the first column
                            with col1:
                                st.subheader(f"Original Content")
                                # Save the image temporarily
                                img_path = temp_dir_path / f"preview_page_{page_num}.png"
                                img.save(img_path)
                                st.image(img_path, use_container_width=True)
                            
                            # Display the extracted information in the second column
                            with col2:
                                st.subheader("Extracted Information")
                                page_description = data.get('pages', {}).get(str(page_num), 'No description available')
                                st.markdown(page_description)
                            
                            # Add a separator between pages
                            if i < pages_to_show - 1:
                                st.markdown("---")
                    elif output_file and not PDF_PREVIEW_AVAILABLE:
                        st.warning("PDF preview not available. Install pdf2image package for PDF previews.")
                        # Still show the extracted information
                        with open(output_file, 'r') as f:
                            data = json.load(f)
                            pages = data.get('pages', {})
                            pages_to_show = min(3, len(pages))
                            
                            for i in range(1, pages_to_show + 1):
                                st.markdown(f"#### Page {i}")
                                st.markdown(pages.get(str(i), 'No description available'))
                                if i < pages_to_show:
                                    st.markdown("---")
                
                # Add a separator between files
                st.markdown("---")
            
            # Option to view all output files
            with st.expander("View All Output Files"):
                for output_file in all_output_files:
                    st.write(f"- {output_file}")
    
    except Exception as e:
        st.error(f"Error: {e}")
        st.error("Make sure Ollama is running and the specified model is available.")

# Information section
st.header("How to Use")
st.markdown("""
1. Configure the Ollama model and API URL in the sidebar
2. Customize the prompt if needed
3. Select an output directory
4. Upload one or more images or PDFs
5. Click "Process Files" to start processing
6. View the results in the specified output directory
""")

st.header("Requirements")
st.markdown("""
- Ollama must be installed and running locally
- The specified vision model must be available in Ollama
- For PDF processing, poppler must be installed:
  - macOS: `brew install poppler`
  - Ubuntu/Debian: `apt-get install poppler-utils`
  - Windows: Download from the poppler releases page and add to PATH
""")

# Footer
st.markdown("---")
st.markdown("Files2Knowledge - Convert images and PDFs to semantic descriptions using Ollama") 