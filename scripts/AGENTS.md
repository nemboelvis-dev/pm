# Server scripts

`start.ps1` and `stop.ps1` support Windows PowerShell. `start.sh` and `stop.sh` support both macOS and Linux. They resolve the repository root from their own location and delegate all application configuration to the root `compose.yaml` file.

Keep these scripts as thin Docker Compose wrappers and ensure they fail immediately when Docker returns an error.
