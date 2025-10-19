# Issue Analyzer - Quick Guide

## What It Does

Automates analysis of tax calculation discrepancies from GitHub issues:

1. Downloads TaxAct PDFs and PolicyEngine outputs from taxsim.nber.org
2. Extracts values from both systems
3. Finds discrepancies
4. (Optional) Uses Claude AI to analyze which is correct and suggest fixes

## Setup

### 1. Install Dependencies
```bash
cd policyengine-taxsim
pip install -e .
```

### 2. Set API Key (Optional - for AI analysis)
```bash
export ANTHROPIC_API_KEY="sk-ant-your-key-here"
```

⚠️ **Security:** Never commit API keys. This is in `.gitignore`.

## Usage

### Basic Analysis (No AI)
```bash
python policyengine_taxsim/cli.py analyze-issue 596
```

**This will:**
- Download files from taxsim.nber.org/out2psl/596/
- Parse TaxAct PDFs
- Parse PolicyEngine output.txt
- Find discrepancies
- Save results to `issue_analysis_596/`

### With AI Analysis
```bash
python policyengine_taxsim/cli.py analyze-issue 596 --use-llm
```

**Additionally does:**
- Calls Claude API to analyze each discrepancy
- Determines which system is correct
- Suggests code fixes
- Costs ~$0.25-0.50 per issue

## What You Get

```
issue_analysis_596/
├── results/
│   ├── analysis_results.json    # Complete data
│   └── SUMMARY.md               # Human-readable summary
└── attachments/
    ├── *.pdf                    # TaxAct forms
    ├── output.txt               # PolicyEngine output
    └── txpydata.csv             # Input data
```

## Example Output

```
═══════════════════════════════════════
  Issue Analysis for #596
═══════════════════════════════════════

📥 Step 1: Fetching GitHub issue...
   ✓ Title: MN Joint 2024 marriage credit question
   ✓ Author: feenberg

📥 Step 2: Downloading from taxsim.nber.org...
   ✓ Downloaded 8 files

🔍 Step 3: Parsing TaxAct PDFs...
   ✓ Extracted 15 values from 4 PDFs

🔍 Step 4: Parsing PolicyEngine output...
   ✓ Extracted 23 values from output.txt

⚖️  Step 5: Finding discrepancies...

⚠️  Found 1 discrepancy(ies)

1. marriage_credit
   TaxAct:       $144.00
   PolicyEngine: $247.22
   Difference:   $103.22

🤖 Step 6: Running AI analysis...

📊 Analysis Results:

Variable: marriage_credit
Verdict: TaxAct is correct
✓ Fix suggested

✅ Analysis complete!
```

## Workflow

```
Issue Created
     ↓
You run: python policyengine_taxsim/cli.py analyze-issue 596 --use-llm
     ↓
Tool downloads & parses everything
     ↓
AI analyzes and suggests fixes
     ↓
You review SUMMARY.md
     ↓
You apply the fix to policyengine-us
     ↓
Done!
```

## Time Savings

**Before:** 1-2 hours manual work
**After:** 15-20 minutes (mostly review)

## Security

- ✅ API keys from environment only
- ✅ `issue_analysis_*` in `.gitignore`
- ✅ Never commits tokens or analysis output
- ⚠️ Always run `git status` before committing

## Troubleshooting

**"ANTHROPIC_API_KEY not set"**
```bash
export ANTHROPIC_API_KEY="your-key"
```

**"No PDFs found"**
- Check if taxsim.nber.org/out2psl/N/ exists for your issue

**PDF parsing returns no values**
- PDF may not have form fields
- Try without --use-llm to see raw data

## What's Not Automated (Yet)

- ❌ Applying the fix to policyengine-us (you do this manually)
- ❌ Running tests on the fix (you do this)
- ❌ Creating the PR (you do this)

The tool gives you the analysis and suggested fix - you apply it.

## Cost

- Basic analysis: Free
- With AI (`--use-llm`): ~$0.25-0.50 per issue (Claude API)

## Examples

**Just find discrepancies:**
```bash
python policyengine_taxsim/cli.py analyze-issue 596
cat issue_analysis_596/results/SUMMARY.md
```

**Get AI analysis:**
```bash
python policyengine_taxsim/cli.py analyze-issue 596 --use-llm
cat issue_analysis_596/results/SUMMARY.md
# Review suggested fixes in analysis_results.json
```

**Clean up after:**
```bash
# Copy what you need
cp issue_analysis_596/results/SUMMARY.md ~/notes/

# Delete the rest
rm -rf issue_analysis_596/
```

## Support

- Issues: https://github.com/PolicyEngine/policyengine-taxsim/issues
- Main README: [../README.md](../README.md)
