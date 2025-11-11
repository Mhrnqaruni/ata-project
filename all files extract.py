import os
import logging

# --- Configuration ---
# The directory to start the search from. '.' means the current directory.
ROOT_DIRECTORY = '.'

# The name of the output file.
OUTPUT_FILENAME = 'output.txt'

# The file extensions to look for.
TARGET_EXTENSIONS = ['.py', '.jsx', '.js', '.html']

# List of directory names to exclude from the search.
EXCLUDED_DIRECTORIES = ['venv', '.git', 'node_modules', '.pytest_cache', '__pycache__']

# The name of the log file.
LOG_FILENAME = 'script.log'
# --- End of Configuration ---

def setup_logging():
    """Configures the logging for the script."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(LOG_FILENAME),
            logging.StreamHandler()
        ]
    )

def collect_files_and_content():
    """
    Traverses subdirectories, reads specified files, and writes their
    content to an output file, skipping excluded directories.
    """
    logging.info(f"Starting the script in directory: {os.path.abspath(ROOT_DIRECTORY)}")
    logging.info(f"Looking for files with extensions: {', '.join(TARGET_EXTENSIONS)}")
    logging.info(f"Excluding directories named: {', '.join(EXCLUDED_DIRECTORIES)}")
    logging.info(f"Output will be saved to: {OUTPUT_FILENAME}")

    try:
        with open(OUTPUT_FILENAME, 'w', encoding='utf-8') as outfile:
            # os.walk recursively goes through directories.
            for dirpath, dirnames, filenames in os.walk(ROOT_DIRECTORY):
                
                # --- FILTERING LOGIC ---
                # Modify dirnames in-place to prevent os.walk from descending into them.
                # The `[:]` is crucial for modifying the list in-place. [1]
                dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRECTORIES]
                
                logging.info(f"Scanning directory: {dirpath}")
                for filename in filenames:
                    # Check if the file has one of the target extensions.
                    if any(filename.endswith(ext) for ext in TARGET_EXTENSIONS):
                        file_path = os.path.join(dirpath, filename)
                        logging.info(f"Found matching file: {file_path}")

                        try:
                            # Write the file path to the output file.
                            outfile.write(f"--- File: {file_path} ---\n\n")
                            
                            # Open and read the content of the found file.
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as infile:
                                content = infile.read()
                                outfile.write(content)
                                outfile.write("\n\n")
                        except Exception as e:
                            logging.error(f"Could not read file {file_path}: {e}")
                            outfile.write(f"--- Error reading file: {file_path} ---\n\n")

    except IOError as e:
        logging.critical(f"Could not write to output file {OUTPUT_FILENAME}: {e}")

    logging.info("Script has finished execution.")

if __name__ == "__main__":
    setup_logging()
    collect_files_and_content()