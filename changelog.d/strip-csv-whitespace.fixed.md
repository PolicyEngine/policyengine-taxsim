Strip whitespace from CSV column headers on input so columns with leading/trailing spaces (e.g. ` ltcg ,`) are recognized rather than silently dropped, matching what TAXSIM-style users expect.
