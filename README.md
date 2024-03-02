# Project Title

Brief description of your project.

## Getting Started

These instructions will get you a copy of the project up and running on your local machine for development and testing purposes.

### Prerequisites

- [Conda](https://docs.conda.io/projects/conda/en/latest/user-guide/install/) must be installed on your system.
- [Git](https://git-scm.com/downloads) (optional, if you're cloning the repository)

### Setup for macOS Users

If you are using a macOS, you must run the `mac_os_start.sh` script first. This script prepares your macOS environment for the project. Open your terminal and execute the following command in the project's root directory:

```bash
./mac_os_start.sh
```

## Creating the Conda Environment

Create a Conda environment using the provided `environment.yml` file. This file includes all the necessary dependencies for the project. Run the following command in the project's root directory:

```bash
conda env create -f environment.yml
```
Then
```bash
conda activate master_server
```

### Running the Application

With the Conda environment activated, you can start the Flask application by running:

```bash
python task_server.py
```

This command starts the Flask server, and you should see output indicating that the server is running, typically on http://127.0.0.1:8100 or a similar local address.

