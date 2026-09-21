Require policyengine-us>=2.6.17 so pip stops resolving to a version that imports the removed spm_calculator.geoadj module, which broke test collection across CI (PE-US #9442).
