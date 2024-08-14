import pandas as pd

from TaxsimInputReader import InputReader


class TextDescriptionWriter:
    def __init__(self, input_data, InputReader):
        self.input_data = input_data
        self.reader = InputReader
        self.output = self.format_data()
        self.write_to_file()

    # return the full name of the state corresponding to the state number
    def get_state_name(self, state_number):
        state_mapping = {
            1: "Alabama", 2: "Alaska", 3: "Arizona", 4: "Arkansas", 5: "California", 6: "Colorado", 7: "Connecticut",
            8: "Delaware", 9: "District of Columbia", 10: "Florida", 11: "Georgia", 12: "Hawaii", 13: "Idaho",
            14: "Illinois", 15: "Indiana", 16: "Iowa", 17: "Kansas", 18: "Kentucky", 19: "Louisiana", 20: "Maine",
            21: "Maryland", 22: "Massachusetts", 23: "Michigan", 24: "Minnesota", 25: "Mississippi", 26: "Missouri",
            27: "Montana", 28: "Nebraska", 29: "Nevada", 30: "New Hampshire", 31: "New Jersey", 32: "New Mexico",
            33: "New York", 34: "North Carolina", 35: "North Dakota", 36: "Ohio", 37: "Oklahoma", 38: "Oregon",
            39: "Pennsylvania", 40: "Rhode Island", 41: "South Carolina", 42: "South Dakota", 43: "Tennessee",
            44: "Texas", 45: "Utah", 46: "Vermont", 47: "Virginia", 48: "Washington", 49: "West Virginia",
            50: "Wisconsin", 51: "Wyoming"
        }
        return state_mapping.get(state_number)
    
    # return filing status. Taxsim leaves 6 and 5 as blank ()
    def get_filing_status(self, mstat):
        filing_status_map = {
            1: "Single",
            2: "Joint",
            6: "",
            8: "Single",
            5: ""
        }
        return filing_status_map.get(mstat, f"Unknown filing status: {mstat}")
        
    # convert the input data and the output data to dictionaries and get the values corresponding to the left column. Returns 0 if none
    def format_data(self):
        output_df = self.input_data.iloc[0].to_dict()
        input_df = self.reader.df.iloc[0].to_dict()

        state_number = input_df['state']

        state_name = self.get_state_name(state_number)

        mstat = input_df['mstat']
        marital_status = self.get_filing_status(mstat)


        placeholder = "placeholder"


        formatted_output = f"""
Input Data:
    1. Record ID:                    {input_df.get('taxsimid', 0):>5.0f}.
    2. Tax Year:                  {input_df.get('year', 0):>4.2f}
    3. State Code:                      {state_number:>2.0f}.{state_name:<20}
    4. Marital Status:            {input_df.get('mstat', 0):>7.2f} {marital_status:<10}
  5-6. Age (Txpyr/Spouse):        {input_df.get('page', 0):>7.2f}{input_df.get('sage', 0):>11.2f}
    7. Dependent Exemptions:      {placeholder}
 8-10. #deps for CCC/CTC/EIC:     {input_df.get('depx', 0):>7.2f}
11-12. Wages (Txpyr/Spouse):   {input_df.get('pwages', 0):>10.2f}{input_df.get('swages', 0):>11.2f}
11a12a Self-employment income: {input_df.get('psemp', 0):>10.2f}{input_df.get('ssemp', 0):>11.2f}
   13. Dividend Income:           {input_df.get('dividends', 0):>7.2f}
   14. Interest Received:         {input_df.get('intrec', 0):>7.2f}
   15. Short Term Gains:          {input_df.get('stcg', 0):>7.2f}
   16. Long Term Gains:           {input_df.get('ltcg', 0):>7.2f}
   17. Other Property:            {input_df.get('otherprop', 0):>7.2f}
   18. Other Non-Property:        {input_df.get('nonprop', 0):>7.2f}
   19. Taxable Pensions:          {input_df.get('pensions', 0):>7.2f}
   20. Gross Social Security:     {input_df.get('gssi', 0):>7.2f}
21-22. Tot/Txpy/Spouse UI:        {placeholder}
   23. Non-taxable Transfers:     {input_df.get('transfers', 0):>7.2f}
   24. Rent Paid:                 {input_df.get('rentpaid', 0):>7.2f}
   25. Property Taxes Paid:       {input_df.get('proptax', 0):>7.2f}
   26. Other Itemized Deds:       {input_df.get('otheritem', 0):>7.2f}
   27. Child Care Expenses:       {input_df.get('childcare', 0):>7.2f}
   28. Mortgage Interest:         {input_df.get('mortgage', 0):>7.2f}
   29. S-Corp profits:            {input_df.get('scorp', 0):>7.2f}
29 31. Txpy/Spouse QBI w/o PO:    {input_df.get('pbusinc', 0):>7.2f}{input_df.get('sbusinc', 0):>11.2f}
30 32. Txpy/Spouse SSTB w PO:     {input_df.get('pprofinc', 0):>7.2f}{input_df.get('sprofinc', 0):>11.2f}

Basic Output:
     1. Record ID:               {input_df['taxsimid']:>3.0f}.                            
     2. Year:                       {output_df['year']:>8}
     3. State (SOI code):         {state_number:>10.0f}{state_name:>15}             
     4. Federal IIT Liability:      {output_df['fiitax']:>8}
     5. State IIT Liability:        {output_df['siitax']:>8}
     6. SS Payroll Tax Liability:   {output_df['fica']:>8}
Marginal Rates wrt Weighted Average Earnings
     7. Federal Marginal Rate:      {output_df['frate']:>8}
     8. State Marginal Rate:        {output_df['srate']:>8}
     9. Weighed Payroll Tax Rate:   {output_df['tfica']:>8}
                      
Federal Tax Calculation:              Base                    
    10. Federal AGI                {output_df['v10']:>9}    
    11. UI in AGI 1979+            {output_df['v11']:>9}    
    12. Social Security in AGI 84  {output_df['v12']:>9}    
    13. Zero Bracket Amount        {output_df['v13']:>9}    
    14. Personal Exemptions        {output_df['v14']:>9}   
    15. Exemption Phaseout 1991+   {output_df['v15']:>9}    
    16. Deduction Phaseout 1991+   {output_df['v16']:>9}   
    17. Deductions allowed         {output_df['v17']:>9}   
        QBI deduction              {placeholder:>9}    
    18. Federal Taxable Income     {output_df['v18']:>9}    
    19. Federal Regular Tax        {output_df['v19']:>9}    
    20. Exemption Surtax 1988-96   {output_df['v20']:>9}   
    21. General Tax Credit 1975-8  {output_df['v21']:>9}    
    22. Child Tax Credit*17/22 98  {output_df['v22']:>9}   
    23. Refundable Part            {output_df['v23']:>9}   
    24. Child Care Credit 1076+    {output_df['v24']:>9}    
    25. Earned Income Credit 1975  {output_df['v25']:>9}    
    26. Alternative Min Income:    {output_df['v26']:>9}   
    27. AMT                        {output_df['v27']:>9}    
    28. Income Tax Before Credits  {output_df['v28']:>9}   
        Total Credits              {placeholder:>9}   
    29. FICA                       {output_df['v29']:>9}   
        Taxpayer share of FICA     {placeholder:>9}

State Tax Calculation:      
    30. Household Income           {output_df['v30']:>9}    
    31. Imputed Rent               {output_df['v31']:>9}        
    32. AGI                        {output_df['v32']:>9}    
    33. Exemptions                 {output_df['v33']:>9}     
    34. Standard Deduction         {output_df['v34']:>9}     
    35. Itemized Deductions        {output_df['v35']:>9}    
    36. Taxable Income             {output_df['v36']:>9} 
        Tax before credits         {placeholder:>9}        
    37. Property Tax Credit        {output_df['v37']:>9}        
    38. Child Care Credit          {output_df['v38']:>9}        
    39. EIC                        {output_df['v39']:>9}        
        Energy|Fuel Credit         {placeholder:>9}        
        Child Tax Credit           {placeholder:>9}        
    40. Total Credits              {output_df['v40']:>9}        
    41. Bracket Rate               {output_df['v41']:>9}        
        State Tax after Credits    {placeholder:>9}       

    42. QBI Deduction              {placeholder:>9}        

Decomposition of Federal Marginal Rate
    (taxpayer earned income)

Regular Income Tax
    Bracket rate from X,Y or Z      {placeholder:>9}
    Deduction Phaseout:             {placeholder:>9}
    Exemption Phaseout:             {placeholder:>9}
    Social Security Phasein:        {placeholder:>9}
    Child Tax Credit:               {placeholder:>9}
    Child Care Credit:              {placeholder:>9}
    Refundable Part of CTC:         {placeholder:>9}
    Earned Income Credit:           {placeholder:>9}
    Surtax on 15% bracket:          {placeholder:>9}
    Exemption Surtax:               {placeholder:>9}
    Unemployment Insurance:         {placeholder:>9}
    Max Tax on Earned Income:       {placeholder:>9}
    Elderly Credit:                 {placeholder:>9}
    Dependent Care Credit:          {placeholder:>9}
    Percentage Std Deduction:       {placeholder:>9}
    Medicare tax on Unearned Income:{output_df['v43']:>9}
    Cares Recovery Rebates:         {output_df['v45']:>9}
              
Alternative Minimum Income Tax  
    AMT Bracket Rate                {placeholder:>9}
    AMT Phaseout                    {placeholder:>9}

Only Regular Tax Relevant
    Total Marginal Rate:            {placeholder:>9}
    FICA w Medicare (t,s):          {placeholder:>9}{placeholder:>12}
"""
        
        return formatted_output

    # create a new file called text_description_output.txt with the f string
    def write_to_file(self, file_path = "text_description_output.txt"):
        formatted_output = self.format_data()
        with open(file_path, 'w') as file:
            file.write(formatted_output)

        