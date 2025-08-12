import pandas as pd
from abc import ABC, abstractmethod
from typing import Optional, Union
from pathlib import Path


class BaseTaxRunner(ABC):
    """Abstract base class for tax calculation runners
    
    Provides common functionality like sampling, progress tracking,
    and data validation that both PolicyEngine and TAXSIM runners can use.
    """
    
    def __init__(self, input_df: pd.DataFrame):
        """
        Initialize the runner with input data
        
        Args:
            input_df: DataFrame with TAXSIM-format input data
        """
        if not isinstance(input_df, pd.DataFrame):
            raise TypeError("input_df must be a pandas DataFrame")
        
        if len(input_df) == 0:
            raise ValueError("input_df cannot be empty")
        
        self.input_df = input_df.copy()
        self.results = None
        self._validate_input()
    
    def _validate_input(self):
        """Validate that input data has required structure"""
        # Check for taxsimid column (required for all operations)
        if 'taxsimid' not in self.input_df.columns:
            raise ValueError("Input data must contain 'taxsimid' column")
        
        # Check for duplicate taxsimids
        if self.input_df['taxsimid'].duplicated().any():
            raise ValueError("Input data contains duplicate taxsimid values")
    
    @abstractmethod
    def run(self, show_progress: bool = True) -> pd.DataFrame:
        """
        Run tax calculations for all records
        
        Args:
            show_progress: Whether to show progress indicators
            
        Returns:
            DataFrame with tax calculation results
        """
        pass
    
    def sample(self, n: int, random_state: int = 42) -> 'BaseTaxRunner':
        """
        Return new runner with sampled data
        
        Args:
            n: Number of records to sample
            random_state: Random seed for reproducible sampling
            
        Returns:
            New instance of the same runner class with sampled data
        """
        if n <= 0:
            raise ValueError("Sample size must be positive")
        
        if n >= len(self.input_df):
            print(f"Warning: Sample size ({n}) >= data size ({len(self.input_df)}). Returning original data.")
            return self.__class__(self.input_df)
        
        sampled_df = self.input_df.sample(n=n, random_state=random_state)
        return self.__class__(sampled_df)
    
    def save_input(self, output_path: Union[str, Path]):
        """
        Save input data to CSV file
        
        Args:
            output_path: Path where to save the input data
        """
        output_path = Path(output_path)
        self.input_df.to_csv(output_path, index=False)
        print(f"Input data saved to: {output_path}")
    
    def save_results(self, output_path: Union[str, Path], results_df: Optional[pd.DataFrame] = None):
        """
        Save results to CSV file
        
        Args:
            output_path: Path where to save the results
            results_df: Results DataFrame (if None, will run calculations)
        """
        if results_df is None:
            if self.results is None:
                print("Running calculations to generate results...")
                results_df = self.run()
            else:
                results_df = self.results
        
        output_path = Path(output_path)
        results_df.to_csv(output_path, index=False)
        print(f"Results saved to: {output_path}")
    
    def get_record_count(self) -> int:
        """Get number of records in input data"""
        return len(self.input_df)
    
    def get_columns(self) -> list:
        """Get list of column names in input data"""
        return list(self.input_df.columns)
    
    def validate_required_columns(self, required_columns: list) -> tuple:
        """
        Validate that input data contains required columns
        
        Args:
            required_columns: List of column names that must be present
            
        Returns:
            Tuple of (missing_columns, extra_columns)
        """
        input_cols = set(self.input_df.columns)
        required_cols = set(required_columns)
        
        missing_columns = list(required_cols - input_cols)
        extra_columns = list(input_cols - required_cols)
        
        return missing_columns, extra_columns
    
    def describe_data(self) -> dict:
        """
        Get summary statistics about the input data
        
        Returns:
            Dictionary with data description
        """
        description = {
            'record_count': len(self.input_df),
            'column_count': len(self.input_df.columns),
            'columns': list(self.input_df.columns),
            'memory_usage_mb': self.input_df.memory_usage(deep=True).sum() / 1024 / 1024,
        }
        
        # Add year information if available
        if 'year' in self.input_df.columns:
            description['years'] = sorted(self.input_df['year'].unique().tolist())
        
        # Add state information if available  
        if 'state' in self.input_df.columns:
            description['states'] = sorted(self.input_df['state'].unique().tolist())
            description['state_count'] = len(description['states'])
        
        # Add marital status information if available
        if 'mstat' in self.input_df.columns:
            mstat_counts = self.input_df['mstat'].value_counts().to_dict()
            description['marital_status'] = mstat_counts
        
        return description
    
    def print_summary(self):
        """Print a summary of the input data"""
        desc = self.describe_data()
        
        print(f"Tax Runner Data Summary:")
        print(f"  Records: {desc['record_count']:,}")
        print(f"  Columns: {desc['column_count']}")
        print(f"  Memory: {desc['memory_usage_mb']:.2f} MB")
        
        if 'years' in desc:
            print(f"  Years: {desc['years']}")
        
        if 'state_count' in desc:
            print(f"  States: {desc['state_count']} different states")
        
        if 'marital_status' in desc:
            print(f"  Marital Status: {desc['marital_status']}")
    
    def filter_by_year(self, year: int) -> 'BaseTaxRunner':
        """
        Filter data by tax year
        
        Args:
            year: Tax year to filter by
            
        Returns:
            New runner instance with filtered data
        """
        if 'year' not in self.input_df.columns:
            raise ValueError("Cannot filter by year: 'year' column not found")
        
        filtered_df = self.input_df[self.input_df['year'] == year].copy()
        
        if len(filtered_df) == 0:
            raise ValueError(f"No records found for year {year}")
        
        return self.__class__(filtered_df)
    
    def filter_by_state(self, state: int) -> 'BaseTaxRunner':
        """
        Filter data by state
        
        Args:
            state: State code to filter by
            
        Returns:
            New runner instance with filtered data
        """
        if 'state' not in self.input_df.columns:
            raise ValueError("Cannot filter by state: 'state' column not found")
        
        filtered_df = self.input_df[self.input_df['state'] == state].copy()
        
        if len(filtered_df) == 0:
            raise ValueError(f"No records found for state {state}")
        
        return self.__class__(filtered_df)
    
    def __len__(self):
        """Return number of records"""
        return len(self.input_df)
    
    def __repr__(self):
        """String representation of the runner"""
        return f"{self.__class__.__name__}(records={len(self.input_df)})"


class ProgressTracker:
    """Utility class for tracking progress during long operations"""
    
    def __init__(self, total: int, description: str = "Processing"):
        self.total = total
        self.description = description
        self.current = 0
    
    def update(self, current: int):
        """Update progress"""
        self.current = current
        percentage = (current / self.total) * 100
        print(f"{self.description}: {current}/{self.total} ({percentage:.1f}%)", end="\r")
    
    def finish(self):
        """Clear progress line and print completion"""
        print("")  # Clear the progress line
        print(f"{self.description} completed: {self.total}/{self.total}")
