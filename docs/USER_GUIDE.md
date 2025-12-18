# Inactive Mailbox Manager - User Guide

This guide provides detailed instructions for using the Inactive Mailbox Manager to manage Microsoft 365 inactive mailboxes at enterprise scale.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Connecting to Exchange Online](#connecting-to-exchange-online)
3. [Viewing Mailboxes](#viewing-mailboxes)
4. [Hold Analysis](#hold-analysis)
5. [Recovery Operations](#recovery-operations)
6. [Restore Operations](#restore-operations)
7. [Bulk Operations](#bulk-operations)
8. [Dashboard and Reporting](#dashboard-and-reporting)
9. [Export Options](#export-options)
10. [Settings and Configuration](#settings-and-configuration)

---

## Getting Started

### First Launch

1. **Terminal UI**: Run `python -m src.ui.app`
2. **Desktop GUI**: Run `python -m src.gui.app`

On first launch, you'll be prompted to configure your connection settings if `config.yaml` doesn't exist.

### Interface Overview

Both interfaces provide access to the same functionality:

| Feature | Terminal UI | Desktop GUI |
|---------|-------------|-------------|
| Mailbox List | Main screen | Mailboxes tab |
| Dashboard | Dashboard screen | Dashboard tab |
| Bulk Operations | Bulk Ops screen | Bulk Operations tab |
| Settings | Settings screen | Settings tab |
| Help | Help screen | Help tab |

---

## Connecting to Exchange Online

### Prerequisites

Before connecting, ensure you have:
- Azure AD App Registration with Exchange.ManageAsApp permission
- Certificate (.pfx) or client secret for authentication
- Exchange Administrator role (for user auth) or app-only permissions

### Connection Methods

#### Method 1: Certificate-Based Authentication (Recommended)

1. Navigate to **Settings**
2. Enter your **Organization** (e.g., `contoso.onmicrosoft.com`)
3. Enter your **Application ID** (from Azure AD)
4. Browse to select your **Certificate File** (.pfx)
5. Enter the certificate password if required
6. Click **Connect**

#### Method 2: Client Secret Authentication

1. Navigate to **Settings**
2. Enter your **Organization**
3. Enter your **Application ID**
4. Enter your **Client Secret**
5. Click **Connect**

### Connection Status

The connection status is displayed in the sidebar (Desktop GUI) or header (Terminal UI):

- **Connected** (Green): Active session to Exchange Online
- **Disconnected** (Red): No active session
- **Connecting** (Yellow): Authentication in progress

### Testing Connection

Click **Test Connection** to verify your credentials without loading mailbox data. This is useful for troubleshooting authentication issues.

---

## Viewing Mailboxes

### Mailbox List

The main mailbox view displays all inactive mailboxes with key information:

| Column | Description |
|--------|-------------|
| Name | Display name of the mailbox owner |
| Email | Primary SMTP address |
| Size | Total mailbox size (GB/MB) |
| Items | Total item count |
| Holds | Active hold types |
| Deleted | Date mailbox became inactive |

### Sorting

Click any column header to sort by that field. Click again to reverse the sort order.

### Filtering

Use the search bar to filter mailboxes by:
- Display name
- Email address
- Hold type

Advanced filters available:
- **Size range**: Filter by mailbox size
- **Hold type**: Show only specific hold types
- **Date range**: Filter by deletion date
- **License type**: Filter by assigned license

### Refreshing Data

- Click **Refresh** to reload data from Exchange Online
- Data is cached locally for performance
- Cache automatically expires after the configured TTL (default: 60 minutes)

---

## Hold Analysis

### Understanding Hold Types

Inactive mailboxes can have various holds preventing permanent deletion:

| Hold Type | Description | Removable |
|-----------|-------------|-----------|
| Litigation Hold | Legal hold placed on mailbox | Yes (Admin) |
| Retention Policy | M365 retention policy | No (Policy-based) |
| eDiscovery Hold | Case-based hold | Yes (eDiscovery Manager) |
| In-Place Hold | Legacy Exchange hold | Yes (Admin) |

### Viewing Hold Details

1. Select a mailbox from the list
2. Click **View Details** or press `d`
3. Navigate to the **Holds** section

The hold hierarchy shows:
- Primary hold type
- Hold duration (if applicable)
- Hold creation date
- Associated retention policy or case

### Hold Impact on Operations

| Hold Status | Can Recover? | Can Restore? | Can Delete? |
|-------------|--------------|--------------|-------------|
| No holds | Yes | Yes | Yes |
| Litigation only | Yes | Yes | No |
| Retention Policy | Yes | Yes | No |
| Multiple holds | Yes | Yes | No |

---

## Recovery Operations

Recovery creates a new active mailbox from an inactive mailbox. The original inactive mailbox remains unchanged.

### Pre-Flight Validation

Before recovery, the system checks for:

1. **UPN Availability**: Target UPN must not exist
2. **SMTP Conflicts**: Primary SMTP must be available
3. **AuxPrimary Shards**: Detects split archive issues
4. **Auto-Expanding Archives**: Identifies complex archive structures
5. **Hold Status**: Warns if holds will affect the new mailbox

### Recovery Wizard Steps

#### Step 1: Select Mailbox
Select the inactive mailbox to recover from the mailbox list.

#### Step 2: Review Details
Review the mailbox information:
- Current size and item count
- Hold status and types
- Archive information
- Recovery eligibility status

#### Step 3: Configure Recovery Options

| Option | Description |
|--------|-------------|
| Target UPN | User Principal Name for new mailbox |
| Target Name | Display name for new mailbox |
| Include Archive | Recover archive mailbox if present |
| Preserve Holds | Apply same holds to new mailbox |

#### Step 4: Validation
The system runs pre-flight checks:
- ✅ UPN available
- ✅ SMTP available
- ✅ No AuxPrimary issues
- ✅ Archive compatible

If any check fails, you'll see details and recommendations.

#### Step 5: Confirm and Execute
Review the recovery summary and click **Recover** to start.

### Recovery Progress

During recovery:
- Progress bar shows completion percentage
- Status messages indicate current operation
- Estimated time remaining displayed

### Post-Recovery

After successful recovery:
- New mailbox is created and active
- User can sign in with new credentials
- Original inactive mailbox remains unchanged
- Audit log records the operation

---

## Restore Operations

Restore merges content from an inactive mailbox into an existing active mailbox. This is useful for retrieving data without creating a new mailbox.

### Restore Prerequisites

- Target mailbox must exist and be active
- You must have permissions on the target mailbox
- Sufficient quota in target mailbox

### Restore Options

| Option | Description |
|--------|-------------|
| Target Mailbox | Active mailbox to receive content |
| Include Folders | Select specific folders to restore |
| Conflict Handling | How to handle duplicate items |
| Include Archive | Restore archive content |

### Conflict Resolution

When items conflict (same subject, date, sender):

| Option | Behavior |
|--------|----------|
| Skip Duplicates | Don't copy conflicting items |
| Create Copies | Copy with modified subject |
| Overwrite | Replace target items |

### Folder Mapping

By default, content restores to matching folder names. Custom mapping available:

```
Source Folder      →  Target Folder
─────────────────────────────────────
Inbox              →  Inbox
Sent Items         →  Sent Items
Deleted Items      →  Restored Items
Custom Folder      →  Restored/Custom Folder
```

---

## Bulk Operations

### Supported Operations

| Operation | Description | CSV Required |
|-----------|-------------|--------------|
| Bulk Export | Export multiple mailbox details | Optional |
| Bulk Recovery | Recover multiple mailboxes | Yes |
| Bulk Restore | Restore multiple mailboxes | Yes |

### CSV Format

#### Bulk Recovery CSV
```csv
SourceMailbox,TargetUPN,TargetName,IncludeArchive
john.smith@contoso.com,john.smith.new@contoso.com,John Smith,true
jane.doe@contoso.com,jane.doe.new@contoso.com,Jane Doe,true
```

#### Bulk Restore CSV
```csv
SourceMailbox,TargetMailbox,IncludeArchive,ConflictAction
john.smith@contoso.com,recovery@contoso.com,true,skip
jane.doe@contoso.com,archive@contoso.com,false,copy
```

### Bulk Operation Workflow

1. **Select Operation Type**
   - Choose Recovery or Restore

2. **Import CSV**
   - Click **Browse** to select your CSV file
   - Preview shows first 20 rows for validation

3. **Validate**
   - System checks all rows for errors
   - Invalid rows highlighted with error messages

4. **Execute**
   - Click **Start** to begin processing
   - Progress bar shows overall completion
   - Individual row status updates in real-time

5. **Results**
   - Summary shows success/failure counts
   - Detailed log available for download
   - Failed items can be exported for retry

### Progress Tracking

During bulk operations:

```
Processing: 45/100 mailboxes
├─ Succeeded: 42
├─ Failed: 2
└─ Remaining: 55

Current: john.smith@contoso.com
Status: Creating mailbox...
ETA: 12 minutes
```

---

## Dashboard and Reporting

### Dashboard Metrics

The dashboard provides at-a-glance statistics:

| Metric | Description |
|--------|-------------|
| Total Mailboxes | Count of all inactive mailboxes |
| Total Storage | Aggregate storage consumption |
| Monthly Cost | Estimated license cost |
| On Hold | Mailboxes with active holds |

### Cost Analysis

#### By License Type
- E5: $38/month per mailbox
- E3: $20/month per mailbox
- F3: $10/month per mailbox

#### By Age Bracket
- 0-30 days
- 31-90 days
- 91-180 days
- 181-365 days
- 1+ years

#### By Organization
Breakdown by operating company or department if organizational attributes are available.

### Charts and Visualizations

Available charts:
- **Pie Chart**: Hold type distribution
- **Bar Chart**: Age distribution
- **Line Chart**: Growth over time
- **Table**: Top mailboxes by size

---

## Export Options

### Export Formats

| Format | Best For | Includes Charts |
|--------|----------|-----------------|
| Excel (.xlsx) | Full analysis | Yes |
| CSV (.csv) | Data processing | No |
| PDF (.pdf) | Reports | Yes |
| JSON (.json) | Integration | No |

### Export Scope

- **Current View**: Export filtered/visible items
- **All Data**: Export complete dataset
- **Selected**: Export selected items only

### Excel Export Contents

The Excel workbook includes multiple sheets:

1. **Summary**: Overview statistics
2. **Mailboxes**: Full mailbox list with details
3. **Holds**: Hold analysis breakdown
4. **Costs**: Cost analysis by various dimensions
5. **Charts**: Visual representations

---

## Settings and Configuration

### Connection Settings

| Setting | Description |
|---------|-------------|
| Organization | M365 tenant domain |
| Application ID | Azure AD app client ID |
| Certificate Path | Path to .pfx certificate |
| Client Secret | Alternative to certificate |

### Appearance Settings

| Setting | Options |
|---------|---------|
| Theme | Dark / Light / System |
| UI Scale | 80% - 150% |

### Export Settings

| Setting | Description |
|---------|-------------|
| Default Format | Preferred export format |
| Include Headers | Add headers to CSV exports |
| Auto-open | Open file after export |

### Cache Settings

| Setting | Description |
|---------|-------------|
| Enable Cache | Use local SQLite cache |
| Cache TTL | Minutes before refresh |
| Clear Cache | Remove cached data |

### Cost Settings

| Setting | Default |
|---------|---------|
| E5 Monthly | $38.00 |
| E3 Monthly | $20.00 |
| F3 Monthly | $10.00 |

---

## Keyboard Shortcuts (Terminal UI)

### Global Navigation

| Key | Action |
|-----|--------|
| `Tab` | Next panel |
| `Shift+Tab` | Previous panel |
| `Escape` | Cancel / Back |
| `q` | Quit application |

### Mailbox List

| Key | Action |
|-----|--------|
| `↑` / `↓` | Navigate rows |
| `Enter` | View details |
| `/` | Focus search |
| `r` | Recover mailbox |
| `t` | Restore mailbox |
| `e` | Export view |
| `d` | View details |

### Dialogs

| Key | Action |
|-----|--------|
| `Enter` | Confirm |
| `Escape` | Cancel |
| `Tab` | Next field |

---

## Tips and Best Practices

### Performance Tips

1. **Use Filtering**: Filter large datasets before export
2. **Enable Caching**: Reduces load on Exchange Online
3. **Bulk Operations**: More efficient than individual operations
4. **Off-Hours**: Run large operations during off-peak hours

### Security Best Practices

1. **Certificate Auth**: More secure than client secrets
2. **Least Privilege**: Use minimum required permissions
3. **Audit Logs**: Regularly review operation logs
4. **Secure Storage**: Protect config.yaml and certificates

### Common Workflows

#### Finding Recoverable Mailboxes
1. Filter by "No holds"
2. Sort by "Deleted" date (oldest first)
3. Export list for approval

#### Cost Reduction Analysis
1. Go to Dashboard
2. Review "By Age Bracket" breakdown
3. Identify mailboxes > 1 year old
4. Export for review with stakeholders

#### Compliance Audit
1. Filter by "Litigation Hold"
2. Export to Excel
3. Include hold details
4. Send to legal team

---

## Getting Help

- **In-App Help**: Press `F1` or navigate to Help tab
- **Troubleshooting Guide**: See [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- **GitHub Issues**: Report bugs or request features

---

*Last Updated: December 2024*
