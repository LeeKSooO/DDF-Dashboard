FROM pytorch/torchserve:0.9.0-cpu

USER root

# Install additional dependencies
RUN pip install --no-cache-dir \
    numpy==1.24.3 \
    scipy==1.11.4 \
    pandas==2.1.3 \
    psycopg2-binary==2.9.7 \
    requests==2.31.0

# Install curl for health check
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Create directories
RUN mkdir -p /home/model-server/model-store \
    /home/model-server/config \
    /home/model-server/models

# Copy configuration and scripts
COPY config/config.properties /home/model-server/config/
COPY model_registration.py /home/model-server/

# Make scripts executable
RUN chmod +x /home/model-server/model_registration.py

# Change ownership
RUN chown -R model-server:model-server /home/model-server

USER model-server

# Set working directory
WORKDIR /home/model-server

# Expose ports
EXPOSE 8080 8081 8082

# Default command with mstgcn model auto-loading
CMD ["torchserve", \
     "--start", \
     "--model-store", "/home/model-server/model-store", \
     "--models", "mstgcn=mstgcn.mar", \
     "--ts-config", "/home/model-server/config/config.properties"]