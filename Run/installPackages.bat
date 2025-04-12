@echo off
echo Installing new Python packages in venv...
cd ..

set VENV_NAME=venv

if not exist "%VENV_NAME%" (
    echo Virtual environment not found. Creating "%VENV_NAME%"...
    py -m venv %VENV_NAME%
    echo Virtual environment created.
) else (
    echo Virtual environment "%VENV_NAME%" already exists.
)

:: Activate the virtual environment
call "%VENV_NAME%\Scripts\activate.bat"

:: Install packages in the activated virtual environment
echo Installing packages from requirements.txt...
pip install -r requirements.txt

echo Installing activfinancial package...
cd ApiWorkKK
pip install activfinancial-1.10.0-py3-none-win_amd64.whl

pause