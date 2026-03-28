# Security Notice

## 🚨 CRITICAL: API Key Exposure

**An OpenAI API key was previously exposed in the `.env` file in this repository.**

### Immediate Actions Required:

1. **Revoke the exposed API key immediately:**
   - Go to https://platform.openai.com/api-keys
   - Find key starting with: `sk-proj-hh67PuZ4p89BZ5wcGhpY...`
   - Click "Revoke" to invalidate it

2. **Generate a new API key:**
   - Create a new key at https://platform.openai.com/api-keys
   - Copy the new key (you'll only see it once)
   - Add it to your local `.env` file (which is now in `.gitignore`)

3. **Verify `.env` is not tracked:**
   ```bash
   git status
   # .env should NOT appear in the list
   ```

### Security Best Practices

**✅ DO:**
- Keep `.env` file local only (it's in `.gitignore` now)
- Use `.env.template` for sharing configuration structure
- Rotate API keys regularly
- Use environment-specific keys (dev/staging/prod)
- Set API key usage limits and monitoring
- Use OAuth or service accounts for production

**❌ DON'T:**
- Commit `.env` or any file containing secrets
- Share API keys via email, chat, or documents
- Use production keys in development
- Hard-code secrets in source files
- Share screenshots containing keys

### Current Security Status

| Component | Status | Notes |
|-----------|--------|-------|
| API Keys | ⚠️ Exposed | **Action required:** Revoke and regenerate |
| `.gitignore` | ✅ Fixed | `.env` now excluded from git |
| IPC Auth | ❌ None | Shared memory uses NULL DACL (any process can access) |
| Input Validation | ⚠️ Partial | Basic validation, needs improvement |
| Logging | ✅ Secure | No secrets logged, proper sanitization |
| HTTPS | N/A | Local IPC only |

### IPC Security Limitations

The current Windows shared memory implementation uses NULL DACL (Discretionary Access Control List):

```cpp
// In shared_memory_manager.cpp
SetSecurityDescriptorDacl(&sd, TRUE, NULL, FALSE);  // NULL = no restrictions
```

**Impact:**
- ANY process on the same machine can read/write shared memory
- No authentication between client and server
- Potential for command injection or data tampering

**Mitigation (TODO):**
- Implement proper Access Control Lists (ACLs)
- Add shared secret authentication
- Validate all commands and responses
- Consider using named pipes with authentication instead

### Reporting Security Issues

If you discover a security vulnerability:

1. **DO NOT** create a public GitHub issue
2. Email the maintainer directly (contact info in README.md)
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

### Security Checklist for Production

Before deploying to production:

- [ ] All exposed API keys revoked and regenerated
- [ ] `.env` file not in version control
- [ ] Environment variables properly configured on server
- [ ] IPC authentication implemented
- [ ] Input validation on all user inputs
- [ ] Rate limiting enabled
- [ ] Logging configured with no secret exposure
- [ ] Error messages don't leak sensitive information
- [ ] Regular security audits scheduled
- [ ] Dependency vulnerability scanning enabled
- [ ] Backup and disaster recovery plan in place

### Dependencies

Regular security updates required for:
- `librosa` - Audio processing
- `sounddevice` - Audio input (native code)
- `PyGLFW` - Window management (native code)
- `pybind11` - Python/C++ bindings

Monitor:
- https://github.com/advisories (GitHub security advisories)
- `pip-audit` for Python dependency vulnerabilities

### Additional Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [OpenAI API Best Practices](https://platform.openai.com/docs/guides/safety-best-practices)
- [CIS Security Benchmarks](https://www.cisecurity.org/cis-benchmarks/)
