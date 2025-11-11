# ---- STAGE 1: BUILDER ----
# Use a full Debian-based Python image that includes the necessary build tools
# (compilers, development headers) to compile Python packages from source.
# Naming this stage "builder" makes it easy to reference later.
FROM python:3.10-bookworm as builder

# Set standard Python environment variables for containerized applications.
# PYTHONDONTWRITEBYTECODE: Prevents Python from writing .pyc files to disk.
# PYTHONUNBUFFERED: Ensures that Python output (like print statements and logs)
# is sent straight to the terminal without being buffered, which is ideal for logging.
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Install system-level dependencies required ONLY for building Python packages.
# - build-essential: Provides compilers (gcc, g++, make).
# - libpq-dev: Provides the development headers for PostgreSQL, needed by psycopg2.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory inside the container.
WORKDIR /usr/src/app

# Upgrade pip to the latest version to ensure compatibility and security.
RUN pip install --upgrade pip

# Copy ONLY the requirements.txt file first. This is a key optimization for
# Docker's layer caching. If requirements.txt doesn't change, Docker will
# reuse the cached layer from the next step, making subsequent builds much faster.
COPY requirements.txt .

# Use "pip wheel" to download and compile all dependencies into a directory
# of .whl (wheel) files. This pre-compiles everything, so the final, slim
# production image does not need any build tools.
RUN pip wheel --no-cache-dir --wheel-dir /usr/src/app/wheels -r requirements.txt


# ---- STAGE 2: FINAL PRODUCTION IMAGE ----
# Start fresh from a "slim" Python image. This image is much smaller because
# it does not include the build tools and development headers from the first stage.
FROM python:3.10-slim-bookworm

# Set the working directory for the final image.
WORKDIR /usr/src/app

# Repeat the standard Python environment variables.
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Temporarily switch to the root user to install system-level packages.
USER root

# Install the RUNTIME system dependencies. These are the libraries the application
# needs to actually run, as opposed to the build-time dependencies.
# - tesseract-ocr: The OCR engine used by pytesseract.
# - libgl1-mesa-glx, libglib2.0-0: Dependencies required by PyMuPDF (fitz) for rendering.
# - libpq5: The runtime library for PostgreSQL, required by psycopg2.
# - libreoffice: For DOCX to PDF conversion (preserves images, tables, formatting).
# - libreoffice-writer: Writer component for document processing.
# - fonts-liberation: Common fonts for better document rendering.
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libpq5 \
    libreoffice \
    libreoffice-writer \
    fonts-liberation \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create a dedicated, non-privileged user to run the application.
# This is a critical security best practice to reduce the container's attack surface.
RUN useradd --create-home appuser

# Copy the pre-compiled Python wheels from the "builder" stage.
COPY --from=builder /usr/src/app/wheels /wheels

# Copy the application's source code and necessary configuration files for migrations.
COPY ./app ./app
COPY ./Books ./Books
COPY alembic.ini .
COPY ./alembic ./alembic

# Install the Python dependencies from the local wheel files. This step is
# extremely fast because no compilation is needed. It also works offline.
RUN pip install --no-cache /wheels/*

# Create the directory where assessment uploads will be stored.
RUN mkdir -p /usr/src/app/assessment_uploads

# Change the ownership of the entire application directory to the non-root user.
# This ensures the application has the correct permissions to run.
RUN chown -R appuser:appuser /usr/src/app

# Switch the active user for all subsequent commands to the new, non-privileged user.
USER appuser

# Expose the port that the application will listen on. Hosting services like
# Railway will map this internal port to a public-facing port.
EXPOSE 8080

# --- [THE FINAL, PRODUCTION-READY COMMAND] ---
# This is the command that will be executed when the container starts.
# It uses `sh -c` to run a sequence of commands.
# 1. `alembic upgrade head`: This command runs the database migrations. It ensures
#    the database schema is up-to-date with the code before the app starts.
#    If migrations fail, the `&&` ensures the server will NOT start, preventing crashes.
# 2. `exec gunicorn ...`: The `exec` command replaces the shell process with the Gunicorn
#    process. This is a best practice that ensures signals (like shutdown commands
#    from Railway) are properly handled by the application server.
#    - `-k uvicorn.workers.UvicornWorker`: Specifies the high-performance Uvicorn worker class.
#    - `-w 4`: Sets the number of worker processes (a good starting point).
#    - `-b 0.0.0.0:${PORT:-8080}`: Binds the server to all available network interfaces on the
#      port specified by the `$PORT` environment variable (standard for hosting platforms)
#      OR defaults to 8080 if `$PORT` is not set (for local Docker runs).
#    - `app.main:app`: Points to the FastAPI application instance inside your code.
CMD ["sh", "-c", "alembic upgrade head && exec gunicorn -k uvicorn.workers.UvicornWorker -w 4 -b 0.0.0.0:${PORT:-8080} app.main:app"]