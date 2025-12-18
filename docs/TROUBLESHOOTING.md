# Inactive Mailbox Manager - Troubleshooting Guide

This guide covers common issues and their solutions when using the Inactive Mailbox Manager.

## Table of Contents

1. [Connection Issues](#connection-issues)
2. [Authentication Errors](#authentication-errors)
3. [Recovery Failures](#recovery-failures)
4. [Hold-Related Issues](#hold-related-issues)
5. [Performance Problems](#performance-problems)
6. [Common Error Messages](#common-error-messages)
7. [PowerShell Issues](#powershell-issues)
8. [UI Issues](#ui-issues)

---

## Connection Issues

### Cannot Connect to Exchange Online

**Symptoms:**
- "Connection failed" error
- Timeout during connection
- "Organization not found" error

**Solutions:**

1. **Verify Organization Name**
   ```
   Correct: contoso.onmicrosoft.com
   Wrong: contoso.com (unless this is your verified domain)
   ```

2. **Check Network Connectivity**
   ```powershell
   # Test connectivity to Exchange Online
   Test-NetConnection outlook.office365.com -Port 443
   ```

3. **Verify PowerShell Module**
   ```powershell
   # Check if Exchange Online module is installed
   Get-Module -ListAvailable ExchangeOnlineManagement

   # Install or update if needed
   Install-Module ExchangeOnlineManagement -Force
   ```

4. **Check Firewall/Proxy**
   - Ensure outbound HTTPS (443) is allowed
   - If using proxy, configure in config.yaml:
     ```yaml
     network:
       proxy: "http://proxy.company.com:8080"
     ```

### Connection Timeout

**Symptoms:**
- Connection takes too long
- "Operation timed out" error

**Solutions:**

1. **Increase Timeout**
   ```yaml
   # config.yaml
   exchange:
     timeout: 600  # Increase from default 300
   ```

2. **Check Exchange Online Health**
   - Visit: https://status.office365.com
   - Check for service incidents

3. **Try During Off-Peak Hours**
   - Large tenants may experience throttling during business hours

### Session Disconnects Frequently

**Symptoms:**
- "Session expired" messages
- Need to reconnect frequently

**Solutions:**

1. **Enable Auto-Reconnect**
   ```yaml
   # config.yaml
   exchange:
     auto_reconnect: true
     reconnect_attempts: 3
   ```

2. **Check Session Timeout Settings**
   - Azure AD sessions have configurable timeouts
   - Contact your Azure AD administrator

---

## Authentication Errors

### Certificate Authentication Failed

**Symptoms:**
- "Certificate not found" error
- "Invalid certificate" error
- "Certificate password incorrect" error

**Solutions:**

1. **Verify Certificate Path**
   ```yaml
   # Use absolute path
   azure:
     certificate_path: "C:/certs/app-cert.pfx"
   ```

2. **Check Certificate Validity**
   ```powershell
   # Check certificate expiration
   $cert = Get-PfxCertificate -FilePath "C:/certs/app-cert.pfx"
   $cert.NotAfter
   ```

3. **Verify Certificate Upload in Azure AD**
   - Go to Azure Portal > App registrations > Your app > Certificates
   - Ensure the public key (.cer) is uploaded

4. **Check Certificate Password**
   - Ensure no special characters are causing issues
   - Try with a simpler password for testing

### Client Secret Authentication Failed

**Symptoms:**
- "Invalid client secret" error
- "Client secret expired" error

**Solutions:**

1. **Check Secret Expiration**
   - Go to Azure Portal > App registrations > Your app > Certificates & secrets
   - Verify the secret hasn't expired

2. **Create New Secret**
   - If expired, create a new secret
   - Update config.yaml with new value

3. **Verify No Extra Characters**
   ```yaml
   # Ensure secret is quoted properly
   azure:
     client_secret: "your-secret-here"
   ```

### Insufficient Permissions

**Symptoms:**
- "Access denied" error
- "Insufficient privileges" error
- Can connect but no mailboxes returned

**Solutions:**

1. **Verify API Permissions**
   - Azure Portal > App registrations > Your app > API permissions
   - Required: Exchange.ManageAsApp (Application)
   - Click "Grant admin consent"

2. **Verify Exchange Role Assignment**
   ```powershell
   # Check role assignments
   Get-ManagementRoleAssignment -RoleAssignee "Your App ID"

   # Assign Exchange Administrator role if needed
   New-ManagementRoleAssignment -Role "Exchange Administrator" -App "Your App ID"
   ```

3. **Check Conditional Access Policies**
   - Ensure your app isn't blocked by CA policies
   - Contact your Azure AD administrator

### MFA Issues

**Symptoms:**
- "MFA required" error
- Cannot complete authentication

**Solutions:**

1. **Use Certificate Authentication**
   - Certificate auth bypasses MFA requirements
   - Recommended for automated/service accounts

2. **Configure App-Only Authentication**
   - Use application permissions instead of delegated
   - Doesn't require user sign-in

---

## Recovery Failures

### UPN Already Exists

**Symptoms:**
- "The user principal name already exists" error
- Validation fails at UPN check

**Solutions:**

1. **Use Different UPN**
   - Modify the target UPN to be unique
   - Example: john.smith.recovered@contoso.com

2. **Check Soft-Deleted Users**
   ```powershell
   # Check for soft-deleted users
   Get-MsolUser -ReturnDeletedUsers | Where-Object {$_.UserPrincipalName -like "*john.smith*"}

   # Permanently delete if needed
   Remove-MsolUser -UserPrincipalName "john.smith@contoso.com" -RemoveFromRecycleBin
   ```

### SMTP Address Conflict

**Symptoms:**
- "Email address already in use" error
- Recovery fails at SMTP validation

**Solutions:**

1. **Check Existing Mailboxes**
   ```powershell
   Get-Mailbox -Filter "EmailAddresses -like '*john.smith@contoso.com*'"
   ```

2. **Check Groups and Contacts**
   ```powershell
   Get-Recipient -Filter "EmailAddresses -like '*john.smith@contoso.com*'"
   ```

3. **Remove Conflicting Address**
   - Remove the address from the existing object
   - Or use a different primary SMTP for recovery

### AuxPrimary Shard Detected

**Symptoms:**
- "AuxPrimary shard detected" warning
- Recovery may fail or be incomplete

**Solutions:**

1. **Understand the Issue**
   - AuxPrimary shards occur when auto-expanding archive splits data
   - Recovery may not include all data

2. **Contact Microsoft Support**
   - Complex AuxPrimary issues may require Microsoft assistance
   - Open a support ticket with mailbox details

3. **Use Restore Instead**
   - Restore operation may handle shards better
   - Restores all content to existing mailbox

### Auto-Expanding Archive Issues

**Symptoms:**
- "Auto-expanding archive detected" warning
- Archive content may be incomplete

**Solutions:**

1. **Include Archive in Recovery**
   - Ensure "Include Archive" option is enabled
   - May require additional processing time

2. **Verify Archive After Recovery**
   ```powershell
   Get-Mailbox -Identity "recovered.user@contoso.com" | Select-Object *archive*
   ```

---

## Hold-Related Issues

### Cannot Delete Mailbox with Hold

**Symptoms:**
- "Mailbox is on hold" error
- Delete operation blocked

**Solutions:**

1. **Identify Hold Types**
   - Use the application's Hold Analysis feature
   - View all holds on the mailbox

2. **Remove Litigation Hold (if authorized)**
   ```powershell
   Set-Mailbox -InactiveMailbox "user@contoso.com" -LitigationHoldEnabled $false
   ```

3. **Contact Legal/Compliance**
   - Holds are often applied for legal reasons
   - Removal may require legal approval

### Retention Policy Preventing Deletion

**Symptoms:**
- Mailbox subject to retention policy
- Cannot remove or modify hold

**Solutions:**

1. **Identify Retention Policy**
   - Check mailbox properties for retention policy
   - Policy may be organization-wide

2. **Exclude from Policy**
   - Work with compliance team to exclude mailbox
   - May require policy modification

3. **Wait for Retention Period**
   - Some policies automatically release after period expires

### eDiscovery Hold

**Symptoms:**
- Mailbox part of eDiscovery case
- Cannot modify mailbox

**Solutions:**

1. **Identify Case**
   - Check Compliance Center for associated cases
   - Contact eDiscovery manager

2. **Release from Case**
   - Only eDiscovery managers can release holds
   - Requires closing or modifying the case

---

## Performance Problems

### Slow Mailbox List Loading

**Symptoms:**
- Loading takes several minutes
- UI becomes unresponsive

**Solutions:**

1. **Enable Caching**
   ```yaml
   # config.yaml
   cache:
     enabled: true
     ttl_minutes: 60
   ```

2. **Reduce Page Size**
   ```yaml
   # config.yaml
   exchange:
     page_size: 500  # Reduce from 1000
   ```

3. **Use Filtering**
   - Apply filters to reduce dataset size
   - Load specific date ranges or hold types

### High Memory Usage

**Symptoms:**
- Application using excessive RAM
- System slowdown

**Solutions:**

1. **Reduce Cache Size**
   ```yaml
   # config.yaml
   cache:
     max_entries: 10000  # Limit cached items
   ```

2. **Clear Cache**
   - Settings > Clear Cache
   - Removes all cached data

3. **Close Unused Windows**
   - Close detail dialogs when not needed
   - Reduce number of open views

### Bulk Operations Slow

**Symptoms:**
- Bulk operations take very long
- Progress seems stuck

**Solutions:**

1. **Reduce Batch Size**
   - Process smaller batches (50 instead of 100)
   - More stable with less timeout risk

2. **Check Exchange Throttling**
   - Large operations may hit throttling limits
   - Add delays between operations:
     ```yaml
     bulk_operations:
       delay_ms: 1000  # 1 second between operations
     ```

3. **Run During Off-Peak**
   - Schedule bulk operations for nights/weekends
   - Less competition for Exchange resources

---

## Common Error Messages

### "Get-Mailbox: The operation couldn't be performed"

**Cause:** Usually permissions or connectivity issue

**Solution:**
1. Verify Exchange Online Management role
2. Check app permissions in Azure AD
3. Test connection to Exchange Online

### "The specified mailbox doesn't exist"

**Cause:** Mailbox may have been permanently deleted

**Solution:**
1. Verify the mailbox GUID/email is correct
2. Check if mailbox is still in inactive state
3. Mailbox may have exceeded retention period

### "The operation timed out"

**Cause:** Exchange Online didn't respond in time

**Solution:**
1. Increase timeout in config.yaml
2. Check Exchange Online service health
3. Retry during off-peak hours

### "Access is denied"

**Cause:** Insufficient permissions

**Solution:**
1. Verify Azure AD app permissions
2. Check Exchange role assignments
3. Ensure admin consent was granted

### "Certificate password is incorrect"

**Cause:** Wrong password for .pfx file

**Solution:**
1. Verify the password
2. Re-export certificate with known password
3. Check for special characters in password

### "The remote server returned an error: (403) Forbidden"

**Cause:** Request blocked by Exchange Online

**Solution:**
1. Check for conditional access policies
2. Verify IP isn't blocked
3. Check for throttling (wait and retry)

---

## PowerShell Issues

### PowerShell Not Found

**Symptoms:**
- "powershell not found" error
- PowerShell commands fail

**Solutions:**

1. **Install PowerShell Core 7+**
   ```
   Download from: https://github.com/PowerShell/PowerShell/releases
   ```

2. **Add to PATH**
   - Ensure PowerShell is in system PATH
   - Default: C:\Program Files\PowerShell\7\

3. **Verify Installation**
   ```cmd
   pwsh --version
   ```

### Exchange Online Module Not Installed

**Symptoms:**
- "ExchangeOnlineManagement module not found" error

**Solutions:**

1. **Install Module**
   ```powershell
   Install-Module ExchangeOnlineManagement -Scope CurrentUser -Force
   ```

2. **Update Module**
   ```powershell
   Update-Module ExchangeOnlineManagement -Force
   ```

3. **Check Module Version**
   ```powershell
   Get-Module ExchangeOnlineManagement -ListAvailable
   # Should be v3.0.0 or higher
   ```

### Execution Policy Blocking

**Symptoms:**
- "Running scripts is disabled" error

**Solutions:**

1. **Set Execution Policy**
   ```powershell
   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
   ```

2. **Or Bypass for Session**
   ```powershell
   powershell -ExecutionPolicy Bypass
   ```

---

## UI Issues

### Terminal UI Not Displaying Correctly

**Symptoms:**
- Garbled characters
- Layout broken
- Colors not showing

**Solutions:**

1. **Use Compatible Terminal**
   - Windows Terminal (recommended)
   - PowerShell 7 native terminal
   - Avoid legacy Command Prompt

2. **Check Terminal Settings**
   - Font: Use a monospace font with Unicode support
   - Example: Cascadia Code, Consolas

3. **Enable Virtual Terminal**
   ```cmd
   # For legacy terminals
   reg add HKCU\Console /v VirtualTerminalLevel /t REG_DWORD /d 1
   ```

### Desktop GUI Not Starting

**Symptoms:**
- Application crashes on start
- No window appears

**Solutions:**

1. **Check CustomTkinter Installation**
   ```bash
   pip install customtkinter --upgrade
   ```

2. **Check for Tkinter**
   ```python
   python -c "import tkinter; print(tkinter.TkVersion)"
   ```

3. **Check Error Log**
   - Review logs/app.log for errors
   - Look for import or initialization errors

### Theme Not Applying

**Symptoms:**
- Colors appear wrong
- Dark theme not working

**Solutions:**

1. **Reset Theme Setting**
   - Settings > Appearance > Theme > Dark
   - Restart application

2. **Check System Theme**
   - "System" theme follows Windows settings
   - Try explicit "Dark" or "Light"

---

## Getting More Help

### Log Files

Logs are located in the `logs/` directory:
- `app.log` - Application errors and info
- `audit.log` - Operation audit trail
- `powershell.log` - PowerShell execution details

### Debug Mode

Enable verbose logging:
```yaml
# config.yaml
logging:
  level: "DEBUG"
```

### Support Resources

1. **GitHub Issues**: Report bugs at the project repository
2. **User Guide**: See [USER_GUIDE.md](USER_GUIDE.md)
3. **Microsoft Docs**: [Exchange Online PowerShell](https://docs.microsoft.com/en-us/powershell/exchange/)

---

*Last Updated: December 2024*
