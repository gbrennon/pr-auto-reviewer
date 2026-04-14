# Troubleshooting

## Common Issues

### "No repos found"

**Cause:** Missing `read:user` scope on token.

**Fix:** Regenerate token with both `repo` and `read:user` scopes.

### "Self-review detected"

**Cause:** Reviewer token belongs to same account as PR author.

**Fix:** Use a different account's token for `FORGEJO_REVIEWER_TOKEN`.

### "Failed to post review"

**Cause:** Invalid reviewer token or wrong username.

**Fix:**
- Verify `FORGEJO_REVIEWER_TOKEN` has `repo` scope
- Check `FORGEJO_REVIEWER_USERNAME` is correct

### "Ollama not available"

**Cause:** Ollama not running or wrong host.

**Fix:**
```bash
# Check Ollama is running
curl http://localhost:11434/api/tags

# Or start Ollama
ollama serve
```

### Service won't start

**Fix:**
```bash
# Check logs
journalctl --user -u pr-ai-auto-reviewer.service --no-pager -f

# Verify config
cat ~/.config/pr-auto-reviewer/config
```

### Token Generation

**Codeberg:** https://codeberg.org/settings/applications

**Forgejo:** `{your-host}/user/settings/applications`

## Getting Help

Check logs for detailed error messages:
```bash
make logs
```