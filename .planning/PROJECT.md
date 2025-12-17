# Inactive Mailbox Manager

## Vision

An enterprise-grade Python application for managing Microsoft 365 inactive mailboxes at scale. This tool fills critical gaps in Microsoft Purview's capabilities—specifically the 5,000 mailbox portal limit and the complete absence of GUI tools for recovery, restore, and bulk operations.

Built for a real-world environment of 80,000+ users across multiple operating companies, this isn't a simple admin utility. It's a comprehensive management platform with brutalist terminal aesthetics, full cost analysis, compliance tracking, and the operational power to handle enterprise-scale inactive mailbox cleanup.

The tool automates what currently requires senior Exchange engineers with deep PowerShell expertise, making these operations accessible while maintaining full auditability and pre-flight validation to prevent costly mistakes.

## Problem

**Microsoft Purview's limitations are blocking enterprise operations:**

- Portal caps at 5,000 inactive mailboxes—useless for large organizations
- Recovery, restore, and delete operations require raw PowerShell—no GUI exists
- No visual identification of hold types (Retention Policy, Litigation Hold, eDiscovery, etc.)
- Zero cost analysis or license tracking for inactive mailboxes
- Manual CSV workflows for any bulk operation
- Complex hold identification requires chaining multiple cmdlets
- No pre-flight validation—UPN/SMTP mismatches can cause permanent deletion locks
- Risk of failed recoveries due to undiscovered AuxPrimary shards or auto-expanding archives

**Target users are senior technical staff:**
- Senior Exchange Engineers
- M365 Administrators
- Compliance Officers
- IT Operations Teams
- Finance (cost analysis stakeholders)

**The pain is real:** Teams currently spend 30+ minutes just identifying inactive mailboxes, 15+ minutes per recovery operation, and have no visibility into the tens of thousands of dollars in monthly license costs sitting in inactive mailboxes.

## Success Criteria

How we know this worked:

- [ ] Connect to Exchange Online and list ALL inactive mailboxes (>5,000) without portal limitations
- [ ] Display mailbox inventory in both terminal and desktop interfaces with full sorting/filtering
- [ ] Identify all hold types for any selected mailbox with visual hierarchy
- [ ] Calculate and display total monthly/annual cost across all inactive mailboxes
- [ ] Export filtered results to formatted Excel workbooks
- [ ] Pre-flight validation detects recovery blockers (AuxPrimary, auto-expanding archives)
- [ ] Guided recovery wizard creates new active mailbox from inactive with full validation
- [ ] Restore operation merges inactive mailbox content into existing mailbox
- [ ] Bulk operations handle 100+ mailboxes with real-time progress tracking
- [ ] Full audit trail logs every operation for compliance
- [ ] Cost dashboard shows breakdown by license type, operating company, age bracket
- [ ] Brutalist terminal theme with full keyboard navigation
- [ ] Desktop GUI provides same functionality with richer visualizations
- [ ] User guide and troubleshooting documentation complete

## Scope

### Building

**Core Infrastructure:**
- PowerShell executor with connection management, auto-reconnect, MFA support
- SQLite local caching layer with configurable refresh
- MSAL Azure AD authentication
- Comprehensive audit logging

**Mailbox Operations:**
- Full inventory retrieval (bypassing 5,000 limit)
- Hold type analysis with visual hierarchy
- Recovery wizard with pre-flight validation
- Restore to existing mailbox with conflict handling
- Bulk operations from CSV with progress tracking

**Cost Analysis:**
- License cost tracking (E5/E3/F3)
- Per-mailbox and aggregate cost calculations
- Cost breakdown by operating company, department, age bracket
- Trend analysis and projections
- Excel/PDF export with charts

**User Interfaces:**
- Terminal UI (Textual) - brutalist dark theme, keyboard-driven
- Desktop GUI (PyQt6 or CustomTkinter) - tabbed interface, same dark aesthetic

**Compliance & Reporting:**
- Full operation audit trail
- Compliance dashboard
- Export to CSV/JSON for SIEM integration

### Not Building

- Multi-user role-based access control (v1.x)
- SharePoint/OneDrive inactive data management
- Real-time alerts via Teams/Slack
- ML-based cleanup recommendations
- Mobile app or web portal
- ITSM integration (ServiceNow, Jira)
- Automated compliance report generation for external auditors

## Context

**Greenfield project** - no existing codebase.

**Tech stack specified:**
- Python 3.10+
- PowerShell Core 7.x with Exchange Online Module
- Textual (terminal UI), PyQt6 or CustomTkinter (desktop GUI)
- SQLite (local cache, audit)
- MSAL for Azure AD auth
- pandas, openpyxl for data processing
- Rich for terminal formatting
- YAML/TOML for configuration

**Target environment:**
- Windows 10/11 or Windows Server 2019+
- Enterprise M365 tenant with 80,000+ users
- Multiple operating companies (organizational segmentation)

**Deployment:**
- Standalone executable via PyInstaller (primary)
- pip install from repo (for IT teams)

## Constraints

- **Platform**: Windows only (PowerShell + Exchange Online Module dependency)
- **Authentication**: Must support MFA and conditional access policies
- **Performance**: Cold start <10s, list 10K mailboxes in <5s from cache, refresh 10K in <2 minutes
- **Security**: No plaintext password storage, all auth via MSAL, full audit trail
- **Reliability**: Auto-reconnect on timeout, retry logic with exponential backoff

## Decisions Made

Key decisions from project exploration:

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Primary UI | Terminal (Textual) | Matches target user expertise, keyboard-driven efficiency |
| Secondary UI | Desktop (PyQt6/CustomTkinter) | Richer visualizations, easier for non-technical stakeholders |
| Data storage | SQLite | Local cache, no external dependencies, portable |
| PowerShell integration | subprocess | Direct control, better error handling than PSSession |
| Authentication | MSAL | Modern auth, MFA support, Azure AD integration |
| Design aesthetic | Brutalist dark | Terminal green on black, maximum density, minimal chrome |
| Phases | All 5 | Full implementation as specified |

## Open Questions

Things to figure out during execution:

- [ ] PyQt6 vs CustomTkinter for desktop GUI - evaluate both during Phase 4
- [ ] Specific license cost values - confirm with finance (using $38 E5, $20 E3, $10 F3 as defaults)
- [ ] Azure AD App Registration details - document setup process
- [ ] Operating company attribute source - which AD attribute contains this?
- [ ] Scheduling mechanism for bulk operations - Windows Task Scheduler vs built-in?

---
*Initialized: 2025-12-17*
*Source: inactive_mailbox_manager_spec.md*
