# Inactive Mailbox Manager

An enterprise-grade Python application for managing Microsoft 365 inactive mailboxes at scale. This tool fills critical gaps in Microsoft Purview's capabilities, specifically the 5,000 mailbox portal limit and the absence of GUI tools for recovery, restore, and bulk operations.

## Features

### Core Capabilities
- **Bypass Portal Limits**: List and manage ALL inactive mailboxes (80,000+) without Microsoft Purview's 5,000 limit
- **Hold Analysis**: Identify all hold types (Litigation, Retention Policy, eDiscovery, In-Place) with visual hierarchy
- **Recovery Wizard**: Guided workflow to recover inactive mailboxes to new active mailboxes with pre-flight validation
- **Restore Operations**: Merge inactive mailbox content into existing mailboxes with conflict handling
- **Bulk Operations**: Process 100+ mailboxes from CSV with real-time progress tracking

### Cost Analysis
- License cost tracking (E5/E3/F3)
- Per-mailbox and aggregate cost calculations
- Cost breakdown by operating company, department, and age bracket
- Excel/PDF export with charts and visualizations

### Dual Interface
- **Terminal UI**: Brutalist dark theme with full keyboard navigation (Textual)
- **Desktop GUI**: Modern dark interface with the same functionality (CustomTkinter)

### Enterprise Features
- Full audit trail for compliance
- SQLite local caching for performance
- Auto-reconnect on session timeout
- MFA and conditional access support via MSAL

## Requirements

### System Requirements
- Windows 10/11 or Windows Server 2019+
- Python 3.10 or higher
- PowerShell Core 7.x
- Exchange Online Management Module v3+

### Azure AD Requirements
- Azure AD App Registration with the following API permissions:
  - Exchange.ManageAsApp (Application)
  - Or user authentication with Exchange Administrator role

## Installation

### 1. Clone the Repository
```bash
git clone https://github.com/your-org/inactive-mailbox-manager.git
cd inactive-mailbox-manager
```

### 2. Create Virtual Environment
```bash
python -m venv venv
venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Install PowerShell Module
```powershell
Install-Module -Name ExchangeOnlineManagement -Scope CurrentUser -Force
```

### 5. Configure Azure AD App
Create an Azure AD App Registration:
1. Go to Azure Portal > Azure Active Directory > App registrations
2. Create new registration
3. Add API permission: Office 365 Exchange Online > Exchange.ManageAsApp
4. Create client secret or upload certificate
5. Note the Application (client) ID and Tenant ID

### 6. Create Configuration
```bash
copy config.example.yaml config.yaml
```

Edit `config.yaml` with your Azure AD details:
```yaml
azure:
  tenant_id: "your-tenant-id"
  client_id: "your-client-id"
  certificate_path: "path/to/cert.pfx"  # Or use client_secret

exchange:
  organization: "your-org.onmicrosoft.com"

costs:
  e5_monthly: 38.00
  e3_monthly: 20.00
  f3_monthly: 10.00
```

## Quick Start

### Terminal UI
```bash
python -m src.ui.app
```

### Desktop GUI
```bash
python -m src.gui.app
```

### Keyboard Navigation (Terminal UI)

| Key | Action |
|-----|--------|
| `Tab` | Navigate between panels |
| `Enter` | Select/confirm |
| `Escape` | Cancel/back |
| `/` | Quick search |
| `r` | Recover selected mailbox |
| `d` | View details |
| `e` | Export current view |
| `q` | Quit |

## Project Structure

```
inactive-mailbox-manager/
├── src/
│   ├── core/                   # Business logic
│   │   ├── powershell_executor.py
│   │   ├── exchange_connection.py
│   │   ├── mailbox_service.py
│   │   ├── hold_analyzer.py
│   │   ├── recovery_wizard.py
│   │   ├── restore_service.py
│   │   ├── bulk_operations.py
│   │   ├── cost_calculator.py
│   │   └── dashboard_service.py
│   ├── data/                   # Data layer
│   │   ├── models.py
│   │   ├── database.py
│   │   ├── session.py
│   │   └── audit_logger.py
│   ├── ui/                     # Terminal UI (Textual)
│   │   ├── app.py
│   │   └── screens/
│   ├── gui/                    # Desktop GUI (CustomTkinter)
│   │   ├── app.py
│   │   ├── frames/
│   │   └── dialogs/
│   └── utils/                  # Utilities
│       ├── config.py
│       ├── authentication.py
│       └── ps_parser.py
├── docs/
│   ├── USER_GUIDE.md
│   └── TROUBLESHOOTING.md
├── config.yaml
├── requirements.txt
└── README.md
```

## Documentation

- [User Guide](docs/USER_GUIDE.md) - Detailed usage instructions
- [Troubleshooting](docs/TROUBLESHOOTING.md) - Common issues and solutions

## Configuration Options

### config.yaml Reference

```yaml
# Azure AD Authentication
azure:
  tenant_id: ""           # Azure AD tenant ID
  client_id: ""           # App registration client ID
  certificate_path: ""    # Path to certificate (preferred)
  client_secret: ""       # Or client secret (less secure)

# Exchange Online
exchange:
  organization: ""        # Tenant domain (org.onmicrosoft.com)
  page_size: 1000        # Mailboxes per API call
  timeout: 300           # Connection timeout (seconds)

# Cost Configuration
costs:
  e5_monthly: 38.00      # E5 license monthly cost
  e3_monthly: 20.00      # E3 license monthly cost
  f3_monthly: 10.00      # F3 license monthly cost
  default_license: "E3"  # Default if unknown

# Cache Settings
cache:
  enabled: true
  ttl_minutes: 60        # Cache refresh interval
  database_path: "data/cache.db"

# Logging
logging:
  level: "INFO"
  file: "logs/app.log"
  audit_file: "logs/audit.log"

# UI Preferences
ui:
  theme: "dark"          # dark or light
  page_size: 50          # Items per page in lists
```

## Screenshots

### Terminal UI
```
┌─────────────────────────────────────────────────────────────────┐
│  INACTIVE MAILBOX MANAGER                          [Connected]  │
├─────────────────────────────────────────────────────────────────┤
│  Mailboxes │ Dashboard │ Bulk Ops │ Settings │ Help            │
├─────────────────────────────────────────────────────────────────┤
│  Search: [_________________]                     Total: 12,847  │
├─────────────────────────────────────────────────────────────────┤
│  Name              │ Email                │ Size    │ Holds     │
│ ─────────────────────────────────────────────────────────────── │
│  John Smith        │ john@contoso.com     │ 2.5 GB  │ Litigation│
│  Jane Doe          │ jane@contoso.com     │ 1.2 GB  │ Retention │
│  ...               │ ...                  │ ...     │ ...       │
└─────────────────────────────────────────────────────────────────┘
```

### Desktop GUI
- Dark brutalist theme with terminal green accents
- Sidebar navigation with connection status
- Data grid with sorting and filtering
- Recovery wizard with step-by-step guidance

## License

MIT License - See LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## Support

For issues and feature requests, please use the GitHub issue tracker.

---

*Built for enterprise-scale M365 management*
