#!/bin/bash
# Script to generate Python code from proto files

set -e

echo "Generating Python code from proto files..."

# Create output directory if it doesn't exist
mkdir -p src/grpc_services/generated

# Generate Python code for all proto files
python -m grpc_tools.protoc \
    -I./protos \
    --python_out=./src/grpc_services/generated \
    --grpc_python_out=./src/grpc_services/generated \
    --pyi_out=./src/grpc_services/generated \
    ./protos/*.proto

# Create __init__.py in generated directory
touch src/grpc_services/generated/__init__.py

echo "Proto files compiled successfully!"
echo "Generated files are in: src/grpc_services/generated/"

# List generated files
ls -la src/grpc_services/generated/
