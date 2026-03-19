import io
import pandas as pd
from typing import List, Dict, Any

class DataExporter:
    """Handles the conversion of mining results into downloadable formats (CSV, XLSX)."""
    
    @staticmethod
    def to_csv(results: List[Dict[str, Any]]) -> bytes:
        if not results:
            return b""
        
        df = pd.DataFrame(results, columns=["marketplace", "link_produto", "link_afiliado"])
        return df.to_csv(index=False).encode("utf-8")

    @staticmethod
    def to_xlsx(results: List[Dict[str, Any]]) -> bytes:
        if not results:
            return b""
            
        df = pd.DataFrame(results, columns=["marketplace", "link_produto", "link_afiliado"])
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Links Coletados")
        return buffer.getvalue()
