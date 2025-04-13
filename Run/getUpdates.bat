@echo off
REM Stash any uncommitted changes
git stash save "Stashing uncommitted changes before pulling"

REM Get the current branch name
for /f "tokens=*" %%i in ('git rev-parse --abbrev-ref HEAD') do set CURRENT_BRANCH=%%i

REM Fetch changes from the remote repository
git fetch origin

REM Pull changes from the current branch
git pull origin %CURRENT_BRANCH%

REM Apply the stashed changes
git stash pop

REM Check for merge conflicts
IF ERRORLEVEL 1 (
    echo Merge conflicts detected. Resolving by accepting changes from remote...

    REM Checkout 'theirs' changes
    git checkout --theirs .
)

echo Changes have been fetched and pulled from the branch: %CURRENT_BRANCH%

call installPackages.bat
pause