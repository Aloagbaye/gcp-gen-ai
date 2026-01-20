# Security Checklist Before Pushing to GitHub

## ✅ Files Already Protected by .gitignore

The following files are **already excluded** from git (via `.gitignore`):
- `*.tfvars` - Contains sensitive Terraform variables
- `*.tfstate` - Contains Terraform state (may include secrets)
- `.terraform/` - Terraform provider cache

## ⚠️ Secrets Found in Codebase

### 1. `infra/terraform.tfvars` (SHOULD BE IGNORED)
**Status**: ✅ Protected by `.gitignore` (`*.tfvars`)

**Contains**:
- `neo4j_password = "oLp2o550Fo2OP_tl5e3lQFVa_OlVBqkp7WuBd2ZMg30"` ⚠️ **SENSITIVE**
- `neo4j_uri = "neo4j+s://e072c79a.databases.neo4j.io"` (may be sensitive)
- `neo4j_user = "neo4j"` (less sensitive but still should be protected)

**Action Required**: 
- ✅ Already in `.gitignore` - **VERIFY** it's not tracked:
  ```powershell
  git ls-files | Select-String "terraform.tfvars"
  ```
  If it shows up, remove it:
  ```powershell
  git rm --cached infra/terraform.tfvars
  ```

### 2. Documentation Files (Placeholders Only)
**Status**: ✅ Safe - Uses placeholders like `<your-neo4j-host>`, `<password>`, `<your_gemini_api_key>`

**Files checked**:
- `README.md` - Uses placeholders ✅
- `DEBUGGING_AND_SCRIPTS.md` - Uses placeholders ✅
- `QUERY_API_EXAMPLES.md` - Uses placeholders ✅

### 3. Scripts
**Status**: ✅ Safe - No hardcoded secrets

**Files checked**:
- `scripts/cleanup-vector-index.ps1` - Uses variables/defaults ✅
- `scripts/cleanup-vector-index.sh` - Uses variables/defaults ✅

### 4. Source Code
**Status**: ✅ Safe - Reads from environment variables

**Files checked**:
- `service/app/rag/llm.py` - Uses `os.getenv("GEMINI_API_KEY")` ✅
- `service/app/rag/graph_neo4j.py` - Uses `os.getenv("NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD")` ✅
- `ingestion/function/main.py` - Uses environment variables ✅

## 🔍 Pre-Push Verification Steps

Run these commands before pushing:

```powershell
# 1. Verify terraform.tfvars is NOT tracked
git ls-files | Select-String "terraform.tfvars"
# Should return nothing

# 2. Check for any hardcoded passwords/API keys
git diff --cached | Select-String -Pattern "(password|PASSWORD|api_key|API_KEY|secret|SECRET|token|TOKEN)\s*[=:]\s*['\`"]?[A-Za-z0-9_-]{20,}" -CaseSensitive:$false
# Should return nothing (or only placeholders)

# 3. Verify .gitignore is working
git check-ignore infra/terraform.tfvars
# Should return: infra/terraform.tfvars

# 4. List all files that WILL be committed
git ls-files
# Review this list - ensure no .tfvars, .env, or secret files
```

## 📝 Recommended Actions

1. **Create `terraform.tfvars.example`** (template without secrets):
   ```hcl
   project_id = "your-project-id"
   region = "us-central1"
   bucket_name = "your-bucket-name"
   cloud_run_image_uri = "your-registry/rag-api:latest"
   neo4j_uri = "neo4j+s://your-neo4j-instance.databases.neo4j.io"
   neo4j_user = "neo4j"
   neo4j_password = "your-password-here"
   ```

2. **Add to `.gitignore`** (if not already there):
   ```
   # Already present:
   *.tfvars
   *.tfvars.json
   ```

3. **If `terraform.tfvars` was previously committed**, remove it from git history:
   ```powershell
   git rm --cached infra/terraform.tfvars
   git commit -m "Remove terraform.tfvars from tracking"
   ```

## ✅ Final Checklist

Before pushing to GitHub:
- [ ] Verified `terraform.tfvars` is NOT tracked by git
- [ ] Verified `.gitignore` includes `*.tfvars`
- [ ] Reviewed `git ls-files` output for any sensitive files
- [ ] Created `terraform.tfvars.example` as a template (optional but recommended)
- [ ] No hardcoded API keys or passwords in source code
- [ ] Documentation uses placeholders, not real values

## 🚨 If Secrets Were Already Committed

If you discover secrets were previously committed:

1. **Rotate the secrets immediately** (change Neo4j password, regenerate API keys)
2. **Remove from git history**:
   ```powershell
   git filter-branch --force --index-filter "git rm --cached --ignore-unmatch infra/terraform.tfvars" --prune-empty --tag-name-filter cat -- --all
   ```
   Or use `git-filter-repo` (recommended):
   ```powershell
   pip install git-filter-repo
   git filter-repo --path infra/terraform.tfvars --invert-paths
   ```
3. **Force push** (if already pushed to remote):
   ```powershell
   git push origin --force --all
   ```
   ⚠️ **Warning**: Only do this if you're the only contributor or coordinate with your team!
