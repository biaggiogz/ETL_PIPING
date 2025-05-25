#!/bin/bash

# Initialize variables
image_name=""
image_tag=""
dockerfile_name=""
container_name=""
built_image=""

function show_menu() {
    clear
    echo "================================"
    echo "Docker Operations Menu"
    echo "================================"
    echo "1. Set Docker Configuration"
    echo "2. Build Docker Image"
    echo "3. Run Docker Container"
    echo "4. Stop and Remove Docker Resources"
    echo "5. Test Docker with curl"
    echo "6. Publish Docker Image"
    echo "7. View Container Logs"
    echo "8. Exit"
    echo "================================"
}

function set_config() {
    echo
    read -p "Enter image name: " image_name
    read -p "Enter image tag: " image_tag
    read -p "Enter Dockerfile name: " dockerfile_name
    read -p "Enter container name: " container_name
    built_image="${image_name}:${image_tag}"
    echo "Configuration saved!"
    read -p "Press Enter to continue..."
}

function build_image() {
    if [ ! -z "$built_image" ]; then
        echo "Current image: $built_image"
        read -p "Build new image? (Y/N): " rebuild
        if [[ $rebuild =~ ^[Yy]$ ]]; then
            read -p "Enter new image name: " image_name
            read -p "Enter new image tag: " image_tag
            built_image="${image_name}:${image_tag}"
        fi
    else
        read -p "Enter image name: " image_name
        read -p "Enter image tag: " image_tag
        built_image="${image_name}:${image_tag}"
    fi
    echo "Building image $built_image with Dockerfile $dockerfile_name..."
    docker build -f "$dockerfile_name" -t "$built_image" --platform linux/arm64 --provenance=false ./
    echo
    read -p "Press Enter to continue..."
}

function run_container() {
    if [ -z "$built_image" ]; then
        echo "Please build the image first (Option 2)."
        read -p "Press Enter to continue..."
        return
    fi
    echo "Running container $container_name from image $built_image..."
    docker run -it -d -p 9000:8080 --env-file .env --name "$container_name" "$built_image"
    echo
    read -p "Press Enter to continue..."
}

function cleanup_docker() {
    echo
    echo "Stopping container $container_name..."
    docker stop "$container_name"
    echo "Removing container $container_name..."
    docker rm "$container_name"
    echo "Removing image $built_image..."
    docker rmi "$built_image"
    echo "Cleanup completed!"
    read -p "Press Enter to continue..."
}

function test_docker() {
    if [ -z "$container_name" ]; then
        echo "Please run the container first (Option 3)."
        read -p "Press Enter to continue..."
        return
    fi
    echo "Testing Docker container with curl..."
    curl -X POST "http://localhost:9000/2015-03-31/functions/function/invocations" \
         -H "Content-Type: application/json" --data-binary @events.json
    echo
    read -p "Press Enter to continue..."
}

function view_logs() {
    if [ -z "$container_name" ]; then
        echo "Please run the container first (Option 3)."
        read -p "Press Enter to continue..."
        return
    fi
    echo "Viewing logs for container $container_name..."
    docker logs "$container_name"
    echo
    read -p "Press Enter to continue..."
}

function publish_docker() {
    if [ -z "$built_image" ]; then
        echo "Please build the image first (Option 2)."
        read -p "Press Enter to continue..."
        return
    fi
    echo "Publishing Docker image to ECR..."
    if [ -z "$AWS_ACCOUNT" ]; then
        echo "AWS_ACCOUNT environment variable is not set"
        read -p "Press Enter to continue..."
        return
    fi
    if [ -z "$AWS_REGION" ]; then
        echo "AWS_REGION environment variable is not set"
        read -p "Press Enter to continue..."
        return
    fi

    docker tag "$built_image" "${AWS_ACCOUNT}.dkr.ecr.${AWS_REGION}.amazonaws.com/spark-serverless:${image_tag}-${image_name}" || {
        echo "Error tagging Docker image"
        read -p "Press Enter to continue..."
        return
    }

    docker push "${AWS_ACCOUNT}.dkr.ecr.${AWS_REGION}.amazonaws.com/spark-serverless:${image_tag}-${image_name}" || {
        echo "Error pushing Docker image"
        read -p "Press Enter to continue..."
        return
    }

    echo
    read -p "Press Enter to continue..."
}

# Main loop
while true; do
    show_menu
    read -p "Enter your choice (1-8): " choice
    case $choice in
        1) set_config ;;
        2) build_image ;;
        3) run_container ;;
        4) cleanup_docker ;;
        5) test_docker ;;
        6) publish_docker ;;
        7) view_logs ;;
        8) echo "Exiting..."; exit 0 ;;
        *) echo "Invalid option"; read -p "Press Enter to continue..." ;;
    esac
done
