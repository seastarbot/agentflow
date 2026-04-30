"""Setup script for AgentFlow."""
from setuptools import setup, find_packages

setup(
    name="agentflow",
    version="0.1.0",
    description="Hybrid Agent-Workflow Execution Framework for Industrial AI",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="Sun Wei",
    author_email="sunwei@hellobit.cn",
    url="https://github.com/seastarbot/agentflow",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    python_requires=">=3.9",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
    extras_require={
        "dev": ["pytest>=7.0", "pytest-cov>=4.0"],
    },
)
