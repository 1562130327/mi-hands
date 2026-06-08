from setuptools import setup, find_packages

setup(
    name="mi-hands",
    version="3.0.0",
    packages=find_packages(),
    install_requires=[
        "uiautomation>=2.0.0",
        "pyautogui>=0.9.54",
        "pyperclip>=1.8.0",
        "pywin32>=300",
        "comtypes>=1.1.0",
        "fastapi>=0.68.0",
        "uvicorn>=0.15.0",
        "mcp>=1.0.0",
        "openai>=1.0.0",
        "pydantic>=2.0.0",
        "pyyaml>=6.0",
        "httpx>=0.24.0",
        "Pillow>=9.0.0",
    ],
    entry_points={
        "console_scripts": [
            "mi-hands=src.v3.mcp.plugin:main",
        ],
    },
    author="MI Hands Team",
    description="MiMo Desktop Control SDK - AI-powered desktop automation with self-evolution",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    python_requires=">=3.10",
)
