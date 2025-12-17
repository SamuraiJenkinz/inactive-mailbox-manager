# Roadmap: Inactive Mailbox Manager

## Overview

Build an enterprise-grade M365 inactive mailbox management tool from the ground up. Starting with PowerShell integration and data foundations, progressing through core mailbox operations, then layering cost analysis and reporting, and finally delivering both terminal and desktop user interfaces with full documentation.

## Domain Expertise

None (Python/Windows/PowerShell project - no matching expertise files)

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3...): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

- [ ] **Phase 1: Foundation** - PowerShell executor, SQLite caching, MSAL authentication, project structure
- [ ] **Phase 2: Core Discovery** - Mailbox inventory, hold analysis, filtering/search, data display
- [ ] **Phase 3: Operations** - Recovery wizard, restore functionality, bulk operations, validation
- [ ] **Phase 4: Cost & Reporting** - Cost calculator, dashboards, visualizations, export manager
- [ ] **Phase 5: Terminal UI** - Textual TUI with brutalist theme, all screens, keyboard navigation
- [ ] **Phase 6: Desktop GUI** - PyQt6/CustomTkinter interface, same functionality, richer visuals
- [ ] **Phase 7: Polish & Docs** - Documentation, error handling, onboarding wizard, testing

## Phase Details

### Phase 1: Foundation
**Goal**: Establish core infrastructure - PowerShell execution engine, SQLite caching layer, Azure AD authentication via MSAL, and project scaffolding
**Depends on**: Nothing (first phase)
**Research**: Likely (PowerShell subprocess integration, MSAL authentication)
**Research topics**: Python-PowerShell subprocess patterns, MSAL library for Python, Exchange Online module connection management
**Plans**: TBD

Plans:
- [ ] 01-01: Project structure and configuration system
- [ ] 01-02: PowerShell executor with connection management
- [ ] 01-03: SQLite caching layer and MSAL authentication

### Phase 2: Core Discovery
**Goal**: Implement mailbox inventory retrieval (bypassing 5K limit), hold type identification and analysis, filtering/search capabilities
**Depends on**: Phase 1
**Research**: Likely (Exchange Online cmdlets, hold type GUIDs)
**Research topics**: Get-Mailbox -InactiveMailboxOnly parameters, InPlaceHolds GUID parsing, retention policy identification, hold hierarchy
**Plans**: TBD

Plans:
- [ ] 02-01: Mailbox inventory and data models
- [ ] 02-02: Hold analyzer with full detection logic
- [ ] 02-03: Filtering, search, and data export

### Phase 3: Operations
**Goal**: Implement recovery wizard with pre-flight validation, restore to existing mailbox, and bulk operations manager
**Depends on**: Phase 2
**Research**: Likely (recovery/restore cmdlets, validation patterns)
**Research topics**: New-Mailbox -InactiveMailbox, New-MailboxRestoreRequest, AuxPrimary shard detection, auto-expanding archive detection
**Plans**: TBD

Plans:
- [ ] 03-01: Pre-flight validation and recovery wizard
- [ ] 03-02: Restore operations and conflict handling
- [ ] 03-03: Bulk operations manager with CSV import

### Phase 4: Cost & Reporting
**Goal**: Implement license cost tracking, cost aggregation by multiple dimensions, visualizations, and export to Excel/PDF
**Depends on**: Phase 2
**Research**: Unlikely (internal calculations, standard charting libraries)
**Plans**: TBD

Plans:
- [ ] 04-01: Cost calculator and license tracking
- [ ] 04-02: Dashboards and visualizations
- [ ] 04-03: Export manager (Excel, PDF, CSV)

### Phase 5: Terminal UI
**Goal**: Build complete Textual-based terminal UI with brutalist dark theme, all functional screens, full keyboard navigation
**Depends on**: Phase 3, Phase 4
**Research**: Likely (Textual framework)
**Research topics**: Textual widgets (DataTable, Input, Button), TCSS styling for brutalist theme, keyboard binding patterns, screen navigation
**Plans**: TBD

Plans:
- [ ] 05-01: Main screen layout and mailbox list view
- [ ] 05-02: Detail views (mailbox, holds, cost dashboard)
- [ ] 05-03: Wizards and bulk operations screens

### Phase 6: Desktop GUI
**Goal**: Build PyQt6 or CustomTkinter desktop interface with same functionality as terminal UI, richer visualizations
**Depends on**: Phase 5 (reuse business logic patterns)
**Research**: Likely (GUI framework evaluation)
**Research topics**: PyQt6 vs CustomTkinter comparison, dark theme implementation, QTableView/Treeview for data grids, chart integration
**Plans**: TBD

Plans:
- [ ] 06-01: Framework selection and main window
- [ ] 06-02: Data views and navigation
- [ ] 06-03: Dialogs, wizards, and charts

### Phase 7: Polish & Docs
**Goal**: Complete documentation (user guide, troubleshooting, PowerShell reference), error handling improvements, onboarding wizard, test coverage
**Depends on**: Phase 5, Phase 6
**Research**: Unlikely (internal documentation, established testing patterns)
**Plans**: TBD

Plans:
- [ ] 07-01: User documentation and guides
- [ ] 07-02: Error handling and onboarding wizard
- [ ] 07-03: Test coverage and final polish

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | 0/3 | Not started | - |
| 2. Core Discovery | 0/3 | Not started | - |
| 3. Operations | 0/3 | Not started | - |
| 4. Cost & Reporting | 0/3 | Not started | - |
| 5. Terminal UI | 0/3 | Not started | - |
| 6. Desktop GUI | 0/3 | Not started | - |
| 7. Polish & Docs | 0/3 | Not started | - |
