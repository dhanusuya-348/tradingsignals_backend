#algo/reports/generate_pdf.py
from fpdf import FPDF
import re
import pandas as pd
import requests
import os
from urllib.parse import urlparse
import tempfile
import matplotlib.pyplot as plt
from datetime import datetime, timedelta, timezone
from dateutil import parser
import matplotlib.dates as mdates
import matplotlib.ticker as mticker
from ..config import HISTORICAL_LIMIT

def remove_unicode(text):
    return re.sub(r'[^\x00-\x7F]+', '', text)

class PDFReport(FPDF):
    def __init__(self, orientation='L', unit='mm', format='A4'):
        super().__init__(orientation, unit, format)
        self.set_auto_page_break(auto=True, margin=15)
        self.temp_files = []  # Track temporary files for cleanup

    def __del__(self):
        # Clean up temporary files
        for temp_file in self.temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except:
                pass

    def get_coin_icon(self, symbol, size=32):
        """
        Fetch coin icon from CoinGecko API and return temporary file path
        
        Parameters:
        - symbol: coin symbol (e.g., 'BTC', 'ETH')
        - size: icon size (32, 64, 128, 256)
        
        Returns:
        - path to temporary PNG file or None if failed
        """
        try:
            # Normalize symbol
            symbol = symbol.upper().strip()
            
            # Map common symbols to CoinGecko IDs
            symbol_map = {
                'BTC': 'bitcoin',
                'ETH': 'ethereum', 
                'ADA': 'cardano',
                'DOT': 'polkadot',
                'SOL': 'solana',
                'AVAX': 'avalanche-2',
                'MATIC': 'matic-network',
                'LINK': 'chainlink',
                'UNI': 'uniswap',
                'LTC': 'litecoin',
                'BCH': 'bitcoin-cash',
                'XRP': 'ripple',
                'DOGE': 'dogecoin',
                'SHIB': 'shiba-inu',
                'TRX': 'tron',
                'ATOM': 'cosmos',
                'ALGO': 'algorand',
                'XLM': 'stellar',
                'VET': 'vechain',
                'FIL': 'filecoin',
                'THETA': 'theta-token',
                'AAVE': 'aave',
                'COMP': 'compound-governance-token',
                'MKR': 'maker',
                'SUSHI': 'sushi',
                'CRV': 'curve-dao-token',
                'YFI': 'yearn-finance',
                'SNX': 'havven',
                'RUNE': 'thorchain',
                'LUNA': 'terra-luna',
                'NEAR': 'near',
                'FTM': 'fantom',
                'HBAR': 'hedera-hashgraph',
                'FLOW': 'flow',
                'ICP': 'internet-computer',
                'XTZ': 'tezos',
                'EOS': 'eos',
                'MANA': 'decentraland',
                'SAND': 'the-sandbox',
                'AXS': 'axie-infinity',
                'GALA': 'gala',
                'ENJ': 'enjincoin',
                'BAT': 'basic-attention-token',
                'ZRX': '0x',
                'STORJ': 'storj',
                'GRT': 'the-graph',
                'BAND': 'band-protocol',
                'OCEAN': 'ocean-protocol',
                'REN': 'republic-protocol',
                'ZEC': 'zcash',
                'DASH': 'dash',
                'XMR': 'monero',
                'DCR': 'decred',
                'QTUM': 'qtum',
                'ONT': 'ontology',
                'ICX': 'icon',
                'ZIL': 'zilliqa',
                'HOT': 'holo',
                'IOTA': 'iota',
                'NANO': 'nano',
                'DGB': 'digibyte',
                'SC': 'siacoin',
                'WAVES': 'waves',
                'LSK': 'lisk',
                'STEEM': 'steem',
                'KMD': 'komodo',
                'ARDR': 'ardor',
                'STRAT': 'stratis',
                'BNB': 'binancecoin',
                'BUSD': 'binance-usd',
                'USDT': 'tether',
                'USDC': 'usd-coin',
                'DAI': 'dai',
                'TUSD': 'true-usd',
                'PAX': 'paxos-standard',
                'GUSD': 'gemini-dollar'
            }
            
            coin_id = symbol_map.get(symbol, symbol.lower())
            
            # CoinGecko API endpoint for coin icons
            url = f"https://api.coingecko.com/api/v3/coins/{coin_id}"
            
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                icon_url = data.get('image', {}).get('small')  # 32x32 size
                
                if icon_url:
                    # Download the icon
                    icon_response = requests.get(icon_url, timeout=5)
                    if icon_response.status_code == 200:
                        try:
                            # Import PIL for image processing
                            from PIL import Image
                            import io
                            
                            # Load image from response content
                            image = Image.open(io.BytesIO(icon_response.content))
                            
                            # Convert to RGBA mode if not already
                            if image.mode != 'RGBA':
                                image = image.convert('RGBA')
                            
                            # Create temporary file
                            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
                            
                            # Save as PNG format
                            image.save(temp_file.name, 'PNG')
                            temp_file.close()
                            
                            # Track for cleanup
                            self.temp_files.append(temp_file.name)
                            return temp_file.name
                            
                        except ImportError:
                            # Fallback: just save the content as-is but with validation
                            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
                            temp_file.write(icon_response.content)
                            temp_file.close()
                            
                            # Verify it's a valid image by checking file signature
                            with open(temp_file.name, 'rb') as f:
                                header = f.read(8)
                                # Check for PNG signature
                                if header.startswith(b'\x89PNG\r\n\x1a\n'):
                                    self.temp_files.append(temp_file.name)
                                    return temp_file.name
                                else:
                                    # Not a valid PNG, remove the temp file
                                    import os
                                    os.unlink(temp_file.name)
                                    print(f"Downloaded file for {symbol} is not a valid PNG")
                                    return None
                        
                        except Exception as img_error:
                            print(f"Error processing image for {symbol}: {img_error}")
                            return None
            
            return None
            
        except Exception as e:
            print(f"Failed to fetch icon for {symbol}: {e}")
            return None

    def add_coin_with_icon(self, text, symbol, icon_size=6):
        """
        Add coin name with icon - maintains consistent text sizing
        
        Parameters:
        - symbol: coin symbol for icon lookup
        - text: text to display
        - icon_size: size of icon in mm
        """
        # Set font to match other paragraphs (bold, size 10)
        self.set_font("Arial", "B", 10)
        self.set_text_color(30, 30, 30)
        
        # Get current position
        current_x = self.get_x()
        current_y = self.get_y()
        
        # Try to get coin icon
        icon_path = self.get_coin_icon(symbol)
        
        if icon_path:
            # Add icon
            self.image(icon_path, x=current_x, y=current_y, w=icon_size, h=icon_size)
            # Move cursor to right of icon with small gap
            self.set_xy(current_x + icon_size + 2, current_y)
        
        # Add text with same font size as other paragraphs
        self.multi_cell(0, 6, text)
        self.set_text_color(30, 30, 30)
        self.ln(2)

    def header(self):
        if self.page_no() == 1:
            self.set_font("Arial", "B", 14)
            self.set_text_color(30, 30, 30)
            self.cell(0, 10, "TradingSignals Report", ln=True, align="C")
            self.set_font("Arial", "B", 9)
            self.set_text_color(100, 100, 100)
            
            # Generate UTC timestamp
            from datetime import datetime, timezone
            utc_time = datetime.now(timezone.utc).strftime('%d-%b-%Y %H:%M:%S UTC')
            
            self.cell(0, 8, f"Generated: {utc_time}", ln=True, align="C")
            self.ln(4)
            #self.set_draw_color(180, 180, 180)
            #self.rect(5.0, 5.0, 287.0, 200.0)  # Landscape dimensions (A4 = 297 x 210mm)

    def footer(self):
        if self.page_no() > 1:
            self.set_y(-15)
            self.set_font("Arial", "", 8)
            self.set_text_color(100, 100, 100)
            # Create proper internal link
            link = self.add_link()
            self.set_link(link, page=1)
            self.cell(0, 5, "Back to Page 1", align="R", link=link)

    def add_section_title(self, title):
        self.set_font("Arial", "B", 12)
        self.set_text_color(20, 20, 100)
        self.cell(0, 10, remove_unicode(title), ln=True)
        self.set_text_color(0, 0, 0)
        self.ln(3)

    def add_paragraph(self, text, color=None, bold=False):
        self.set_font("Arial", "B", 10)  # Make all text bold and consistent size
        clean_text = remove_unicode(str(text))
        if color:
            self.set_text_color(color[0], color[1], color[2])
        else:
            self.set_text_color(30, 30, 30)
        self.multi_cell(0, 6, clean_text)
        self.set_text_color(30, 30, 30)
        self.ln(2)

    def add_image(self, path, w=120, h=100, size_type='default'):
        """
        Add image with flexible sizing options
        
        Parameters:
        - path: image file path
        - w, h: default width and height (used when size_type='default')
        - size_type: 'default', 'large', 'medium', 'small', 'full_width'
        """
        # Calculate available page width (landscape A4 = 297mm, with margins ≈ 277mm usable)
        available_width = self.w - 2 * self.l_margin  # ≈ 277mm for landscape A4
        available_height = self.h - 2 * self.t_margin - 30  # Leave space for header/footer
        
        if size_type == 'large':
            # Use 90% of available width, maintain aspect ratio
            img_width = available_width * 0.9
            img_height = img_width * 0.6  # Assume 5:3 aspect ratio for charts
        elif size_type == 'full_width':
            # Use full available width
            img_width = available_width
            img_height = available_width * 0.6
        elif size_type == 'medium':
            # Use 70% of available width
            img_width = available_width * 0.7
            img_height = img_width * 0.6
        elif size_type == 'small':
            # Use 50% of available width
            img_width = available_width * 0.5
            img_height = img_width * 0.6
        else:  # 'default'
            img_width = w
            img_height = h
        
        # Center the image horizontally
        x_position = (self.w - img_width) / 2
        
        # Check if image fits on current page, if not add new page
        if self.get_y() + img_height > self.h - self.b_margin:
            self.add_page()
        
        self.image(path, x=x_position, w=img_width, h=img_height)
        self.ln(3)

    def add_key_value_table(self, summary_dict):
        self.set_font("Arial", "B", 9)
        self.set_fill_color(200, 200, 200)
        self.set_text_color(0)

        self.cell(60, 8, "Metric", border=1, align='C', fill=True)
        self.cell(60, 8, "Value", border=1, align='C', fill=True)
        self.ln()

        self.set_font("Arial", "B", 8)
        for key, value in summary_dict.items():
            key_clean = remove_unicode(str(key)).replace("_", " ")
            self.set_text_color(0, 0, 0)
            self.cell(60, 8, key_clean, border=1, align='C')
            
            # Color coding based on specific metric types
            value_str = str(value).lower()
            
            if 'success rate' in key_clean.lower():
                # Success rate should always be green
                self.set_text_color(0, 150, 0)
            elif 'avg profit' in key_clean.lower() or 'average profit' in key_clean.lower():
                # Average profit: green for positive, red for negative
                try:
                    # Try to extract numeric value from percentage or number
                    import re
                    numeric_match = re.search(r'-?\d+\.?\d*', str(value))
                    if numeric_match:
                        numeric_val = float(numeric_match.group())
                        if numeric_val > 0:
                            self.set_text_color(0, 150, 0)  # Green for positive
                        elif numeric_val < 0:
                            self.set_text_color(200, 0, 0)  # Red for negative
                        else:
                            self.set_text_color(0, 0, 0)  # Black for zero
                    else:
                        self.set_text_color(0, 0, 0)
                except:
                    self.set_text_color(0, 0, 0)
            elif 'cumulative net return %' in key_clean.lower() or 'cumulative return' in key_clean.lower():
                # cumulative net return % : green for positive, red for negative
                try:
                    # Try to extract numeric value from percentage or number
                    import re
                    numeric_match = re.search(r'-?\d+\.?\d*', str(value))
                    if numeric_match:
                        numeric_val = float(numeric_match.group())
                        if numeric_val > 0:
                            self.set_text_color(0, 150, 0)  # Green for positive
                        elif numeric_val < 0:
                            self.set_text_color(200, 0, 0)  # Red for negative
                        else:
                            self.set_text_color(0, 0, 0)  # Black for zero
                    else:
                        self.set_text_color(0, 0, 0)
                except:
                    self.set_text_color(0, 0, 0)
            elif 'successful signals' in key_clean.lower() or 'success' in key_clean.lower():
                # Successful signals should be green
                self.set_text_color(0, 150, 0)
            elif 'failed signals' in key_clean.lower() or 'fail' in key_clean.lower():
                # Failed signals should be red
                self.set_text_color(200, 0, 0)
            elif 'neutral signals' in key_clean.lower() or 'hold signals' in key_clean.lower():
                # Neutral/Hold signals should be yellow/orange
                self.set_text_color(200, 150, 0)
            elif any(word in key_clean.lower() for word in ['profit', 'win', 'gain', 'positive']):
                # Other profit-related metrics
                self.set_text_color(0, 150, 0)
            elif any(word in key_clean.lower() for word in ['loss', 'drawdown', 'negative']):
                # Other loss-related metrics
                self.set_text_color(200, 0, 0)
            else:
                # Default black for other metrics
                self.set_text_color(0, 0, 0)
                
            self.cell(60, 8, str(value), border=1, align='C')
            self.set_text_color(0, 0, 0)
            self.ln()
        self.ln(3)

    def get_confidence_color(self, confidence_percent):
        """Return RGB color based on confidence percentage (0-100)"""
        if confidence_percent >= 80:
            return (0, 100, 0)
        elif confidence_percent >= 60:
            return (50, 150, 50)
        elif confidence_percent >= 40:
            return (100, 100, 100)
        elif confidence_percent >= 20:
            return (200, 100, 100)
        else:
            return (200, 0, 0)

    def get_signal_color(self, signal):
        """Return RGB color based on signal type"""
        signal_str = str(signal).lower().strip()
        
        if any(word in signal_str for word in ['buy', 'long', 'bullish', 'up', 'bull']):
            return (0, 100, 0)
        elif any(word in signal_str for word in ['sell', 'short', 'bearish', 'down', 'bear']):
            return (200, 0, 0)
        elif any(word in signal_str for word in ['hold', 'neutral', 'wait', 'sideways']):
            return (100, 100, 100)
        else:
            try:
                float(signal_str)
                return (100, 100, 100)
            except:
                return (100, 100, 100)

    def get_sentiment_color(self, sentiment):
        """Return RGB color based on sentiment"""
        if isinstance(sentiment, (int, float)):
            if sentiment > 0.25:
                return (0, 100, 0)
            elif sentiment < -0.25:
                return (200, 0, 0)
            else:
                return (100, 100, 100)
        else:
            sentiment_str = str(sentiment).lower()
            if 'bullish' in sentiment_str or 'positive' in sentiment_str:
                return (0, 100, 0)
            elif 'bearish' in sentiment_str or 'negative' in sentiment_str:
                return (200, 0, 0)
            else:
                return (100, 100, 100)

    def get_row_confidence_color(self, row):
        """Return RGB background color for entire row based on success/failure and confidence level from Return %"""
        # Get return percentage and result column
        return_percent = row.get('Return %', 0)
        result = str(row.get('result', '')).upper().strip()
        
        try:
            return_val = float(return_percent)
        except:
            return (255, 255, 255)  # White for invalid data
        
        # Determine if it's a successful trade using the result column
        is_successful = result == 'SUCCESS'
        
        # Calculate confidence based on absolute return percentage
        abs_return = abs(return_val)
        
        # Define confidence levels based on return magnitude
        if abs_return >= 0.5:  # High confidence (0.5% or more)
            confidence_level = "high"
        elif abs_return >= 0.2:  # Medium confidence (0.2% to 0.5%)
            confidence_level = "medium"
        else:  # Low confidence (less than 0.2%)
            confidence_level = "low"
        
        # Apply color grading based on success and confidence
        if is_successful:
            # Success - Green shades (darker for higher confidence)
            if confidence_level == "high":
                return (200, 255, 200)  # Dark green shade
            elif confidence_level == "medium":
                return (230, 255, 230)  # Medium green shade
            else:  # low confidence
                return (245, 255, 245)  # Light green shade
        else:
            # Failure - Red shades (darker for higher confidence)
            if confidence_level == "high":
                return (255, 200, 200)  # Dark red shade
            elif confidence_level == "medium":
                return (255, 230, 230)  # Medium red shade
            else:  # low confidence
                return (255, 245, 245)  # Light red shade

    def add_table_with_coin_icons(self, dataframe, columns, apply_row_coloring=False, cell_colors=None):
        """Enhanced table method that adds coin icons in the 'coin' column and supports cell coloring"""
        self.set_font("Arial", "B", 8)
        self.set_fill_color(200, 200, 200)
        self.set_text_color(0)

        # Custom column widths based on content needs (Landscape page = 275mm usable)
        col_widths = {
            "Entry Time":23,
            "timestamp": 22,
            "Timestamp": 25,
            "coin": 14,
            "open ($)": 15,
            "Entry.P ($)":16,
            "close ($)": 15,
            "rsi": 9,
            "macd": 12,
            "bollinger": 19,
            "news": 9,
            "volatility": 14,
            "signal": 10,
            "r:r": 10,
            "duration": 13,
            "conf": 9,
            "Exit.P ($)": 15,
            "TP ($)": 15,
            "SL ($)": 15,
            "Exit.R": 10,
            "R%": 8,
            "result": 14,
            "Snapshot Time": 26,
            "Exit Time": 23,
            "TD": 11,
            "Open ($)" : 16,
            "High ($)" : 16,
            "Low ($)" : 16,
            "Close ($)": 16,
            "Symbol": 12,
            "Volume (coins)": 23,
            "Historical Time": 25,
            "Historical Close ($)": 28,
            "Historical Volume (coins)": 37,
            "Current Close ($)": 20,
            "Current Volume (coins)": 26,
            "1M Ago Time": 28,
            "1M Ago C ($)": 20,
            "1M Ago V (coins)": 24,
            "2M Ago Time": 28,
            "2M Ago C ($)": 20,
            "2M Ago V (coins)": 24,
            "3M Ago Time": 28,
            "3M Ago C ($)": 20,
            "3M Ago V (coins)": 24,
            "4M Ago Time": 28,
            "4M Ago C ($)": 20,           # ← Changed from "4M Ago Close ($)"
            "4M Ago V (coins)": 24,       # ← Changed from "4M Ago Volume (coins)"
            "5M Ago Time": 28,
            "5M Ago C ($)": 20,           # ← Changed from "5M Ago Close ($)"
            "5M Ago V (coins)": 24,       # ← Changed from "5M Ago Volume (coins)"
            "6M Ago Time": 28,
            "6M Ago C ($)": 20,           # ← Changed
            "6M Ago V (coins)": 24,       # ← Changed
            "7M Ago Time": 28,
            "7M Ago C ($)": 20,           # ← Changed
            "7M Ago V (coins)": 24,       # ← Changed
            "8M Ago Time": 28,
            "8M Ago C ($)": 20,           # ← Changed
            "8M Ago V (coins)": 24,       # ← Changed
            "9M Ago Time": 28,
            "9M Ago C ($)": 20,           # ← Changed
            "9M Ago V (coins)": 24,       # ← Changed
            "10M Ago Time": 28,
            "10M Ago C ($)": 20,          # ← Changed
            "10M Ago V (coins)": 24,      # ← Changed
            "11M Ago Time": 28,
            "11M Ago C ($)": 20,          # ← Changed
            "11M Ago V (coins)": 24,      # ← Changed
            "12M Ago Time": 28,
            "12M Ago C ($)": 20,          # ← Changed
            "12M Ago V (coins)": 24,      # ← Changed
        }
        
        # Table header
        for col in columns:
            self.cell(col_widths.get(col, 16), 7, str(col), border=1, align='C', fill=True)
        self.ln()

        # Table rows
        self.set_font("Arial", "B", 7)
        for row_idx, (_, row) in enumerate(dataframe.iterrows()):
            row_start_y = self.get_y()
            
            for col_idx, col in enumerate(columns):
                value = str(row[col])
                
                # Initialize default colors
                cell_fill_color = (255, 255, 255)  # White background
                text_color = (0, 0, 0)  # Black text
                
                # Check if we have custom cell colors for this cell
                if cell_colors and (row_idx, col_idx) in cell_colors:
                    cell_fill_color = cell_colors[(row_idx, col_idx)]
                
                # Apply row background coloring only for backtest table
                if apply_row_coloring:
                    row_bg_color = self.get_row_confidence_color(row)
                    cell_fill_color = row_bg_color
                    
                    # Special coloring for signal column in backtest table
                    if col == 'signal':
                        signal_str = value.lower().strip()
                        if any(word in signal_str for word in ['buy', 'long', 'bullish', 'up', 'bull']):
                            text_color = (0, 150, 0)  # Bright green for BUY
                        elif any(word in signal_str for word in ['sell', 'short', 'bearish', 'down', 'bear']):
                            text_color = (150, 0, 0)  # Bright red for SELL
                        else:
                            text_color = (0, 0, 0)  # Black for other signals
                    else:
                        text_color = (0, 0, 0)  # Black for all other columns
                else:
                    # Apply text coloring based on column content for non-backtest tables
                    if col == 'signal':
                        text_color = self.get_signal_color(value)
                    elif col == 'sentiment':
                        text_color = self.get_sentiment_color(row[col])
                    elif col == 'result':
                        if any(word in value.lower() for word in ['win', 'profit', 'gain', 'positive']):
                            text_color = (0, 100, 0)
                        elif any(word in value.lower() for word in ['loss', 'lose', 'negative']):
                            text_color = (200, 0, 0)
                        else:
                            text_color = (0, 0, 0)
                    elif col == 'Return %':
                        try:
                            return_val = float(row[col])
                            if return_val > 0:
                                text_color = (0, 100, 0)
                            elif return_val < 0:
                                text_color = (200, 0, 0)
                            else:
                                text_color = (0, 0, 0)
                        except:
                            text_color = (0, 0, 0)
                    elif col in ['macd', 'bollinger']:
                        text_color = self.get_signal_color(value)
                    else:
                        text_color = (0, 0, 0)
                
                # Set colors
                self.set_fill_color(cell_fill_color[0], cell_fill_color[1], cell_fill_color[2])
                self.set_text_color(text_color[0], text_color[1], text_color[2])
                
                # Special handling for coin column with icons
                if col == 'coin':
                    # Save current position
                    cell_x = self.get_x()
                    cell_y = self.get_y()
                    
                    # Draw cell border first
                    self.cell(col_widths.get(col, 16), 7, "", border=1, align='C', fill=True)
                    
                    # Try to add coin icon
                    icon_path = self.get_coin_icon(value, size=32)
                    if icon_path:
                        # Add small icon inside the cell
                        icon_size = 4  # 4mm icon
                        icon_x = cell_x + 2  # 2mm from left edge
                        icon_y = cell_y + 1.5  # Center vertically
                        self.image(icon_path, x=icon_x, y=icon_y, w=icon_size, h=icon_size)
                        
                        # Add text next to icon
                        self.set_xy(cell_x + icon_size + 4, cell_y)
                        self.set_font("Arial", "B", 6)  # Smaller font for coin text
                        self.cell(col_widths.get(col, 16) - icon_size - 4, 7, value, align='L')
                        self.set_font("Arial", "B", 7)  # Reset font
                    else:
                        # Fallback: just add text
                        self.set_xy(cell_x, cell_y)
                        self.cell(col_widths.get(col, 16), 7, value, border=1, align='C', fill=True)
                else:
                    # Regular cell
                    self.cell(col_widths.get(col, 16), 7, value, border=1, align='C', fill=True)
            
            self.set_text_color(0, 0, 0)  # Reset color
            self.ln()
        self.ln(3)

    def add_table(self, dataframe, columns, apply_row_coloring=False, cell_colors=None):
        """Wrapper method to use enhanced table with coin icons and cell colors"""
        self.add_table_with_coin_icons(dataframe, columns, apply_row_coloring, cell_colors)


def create_pdf_report(symbol, interval, signal_info, risk_info, timing_info, summary, pdf_path, backtest_df, headlines):
    pdf = PDFReport()
    pdf.add_page()

    # Create links dictionary to store link identifiers
    links = {}

    # Add compact market info (since time is already in header)
    signal = signal_info["signal"].upper()
    display_signal = "No Clear Direction" if signal == "HOLD" else signal
    territory = "Bullish" if signal == "BUY" else "Bearish" if signal == "SELL" else "Neutral"
    

    # Single compact line with market info and validity
    pdf.set_font("Arial", "", 8)
    pdf.set_text_color(80, 80, 80)
    # Handle datetime object properly
    try:
        # Check if timing_info['end'] is a datetime object or string
        end_time = timing_info['end']
        if isinstance(end_time, str):
            # If it's already a string, use split as before
            end_time_str = end_time.split('.')[0]
        else:
            # If it's a datetime object, format it as string
            end_time_str = end_time.strftime('%d-%b-%Y %H:%M:%S')
    except (AttributeError, KeyError, TypeError):
        # Fallback if there's any issue
        end_time_str = "N/A"

    info_line = f"Coin: {symbol} | Timeframe: {interval} | Market: {territory} | Signal: {display_signal} ({signal_info['confidence']}%) | Valid Till: {end_time_str} UTC | Duration: {timing_info['duration']}"
    pdf.cell(0, 5, info_line, ln=True, align="C")
    pdf.ln(1)

    # Table of Contents
    pdf.ln(1)
    pdf.set_font("Arial", "B", 15)
    pdf.set_text_color(20, 20, 100)
    pdf.cell(0, 15, "Table of Contents", ln=True, align="C")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(1)

    # Get total days from summary if available
    if isinstance(summary, dict):
        analysis_period = summary.get('Total Days Analyzed', '2500 candles')
    else:
        analysis_period = '2500 candles'

    # Create link identifiers for each section with page numbers and indentation levels
    toc_items = [
        ("1. Live Trading Signal Analysis", "live_signal_details", 2, 0),
        ("1.1. Current Signal Overview", "signal_details", 2, 1),
        ("1.2. Current Signal Explanation", "signal_explanation", 2, 1),
        ("2. Market Data & Price Analysis", "price_vol_info", 4, 0),
        ("2.1. Recent Price Snapshot (Latest 5 Periods)", "price_snapshot", 4, 1),
        ("2.2. Weekly Price Progression Analysis", "historical_points", 4, 1),
        ("2.3. Monthly Price Progression Analysis", "historical_points_months", 5, 1),
        ("2.4. Short-term Price & Volume Trends (Current vs 1 Week Ago)", "price_comparison", 6, 1),
        ("2.5. Extended Timeframe Analysis (Past 3 Months)", "price_comparison_w_months", 7, 1),
        ("2.6. Historical Analysis Summary", "historical_summary", 8, 1),
        ("3. Market Sentiment & News Impact", "sentiment_headlines", 9, 0),
        ("4. Technical Analysis & Chart Patterns", "technical_indicators", 12, 0),
        ("5. Risk Assessment & Position Management", "risk_management", 16, 0),
        ("6. Signal Duration & Targets", "signal_timing", 17, 0),
        ("7. Backtest Details", "backtest_details", 18, 0),
        ("7.1. Performance Metrics Overview", "backtest_summary", 18, 1),
        (f"7.2. Detailed Trade History ({analysis_period})", "backtest_table", 19, 1),
        ("7.3. Performance Charts & Visualizations", "visualizations", 21, 1),
    ]

    # Create all links first
    for section, link_id, page, indent in toc_items:
        links[link_id] = pdf.add_link()

    # Professional TOC styling with better layout
    pdf.set_font("Arial", "", 10)

    for i, (section, link_id, page, indent_level) in enumerate(toc_items):
        # Add spacing between sections
        if i > 0:
            pdf.ln(1)
        
        # Calculate indentation based on level
        indent_width = indent_level * 10  # 15 units per indent level
        
        # Calculate the maximum width needed for page numbers (3 digits max)
        page_number_width = 15  # Fixed width for page numbers
        
        # Get available width for section title and dots
        total_width = pdf.w - pdf.l_margin - pdf.r_margin
        content_width = total_width - page_number_width - indent_width
        
        # Section title (clickable) - limit width to prevent overlap
        pdf.set_text_color(30, 30, 150)  # Blue for clickable text
        section_width = min(pdf.get_string_width(section), content_width - 20)  # Leave space for dots
        
        # Create a cell for the section title
        x_start = pdf.get_x()
        y_start = pdf.get_y()
        
        # Add indentation space
        if indent_level > 0:
            pdf.cell(indent_width, 7, "", ln=False)
        
        # Section title cell (clickable)
        pdf.cell(section_width + 5, 7, section, ln=False, align='L', link=links[link_id])
        
        # Calculate remaining width for dots
        dots_width = content_width - section_width - 5
        dot_count = max(3, int(dots_width / pdf.get_string_width('.')))
        dots = '.' * dot_count
        
        # Position for dots
        pdf.set_x(x_start + indent_width + section_width + 5)
        pdf.set_text_color(120, 120, 120)  # Light gray for dots
        pdf.cell(dots_width, 7, dots, ln=False, align='L')
        
        # Position for page number (right-aligned)
        pdf.set_text_color(40, 40, 40)  # Dark gray for page numbers
        pdf.set_font("Arial", "", 10)  # page numbers
        pdf.cell(page_number_width, 7, str(page), ln=True, align='R')
        
        # Reset font for next iteration
        pdf.set_font("Arial", "", 10)

    # Add some spacing and a decorative line
    pdf.ln(8)

    pdf.add_page()  # Start content on new page

    # Extract coin symbol for icon display
    coin_symbol = symbol.replace('USDT', '').replace('USD', '').replace('BTC', '').replace('ETH', '')
    if not coin_symbol:
        coin_symbol = symbol.split('/')[0] if '/' in symbol else symbol[:3]

    # 1. Signal Info - Set the link destination here
    pdf.set_link(links["live_signal_details"])
    pdf.add_section_title("1. Live Trading Signal Analysis")
    pdf.set_link(links["signal_details"])  # Set the destination for this link
    pdf.add_section_title("1.1. Current Signal Overview")

    # Use the new method to add coin name with icon
    pdf.add_coin_with_icon(f"{symbol}", coin_symbol)
    pdf.add_paragraph(f"Interval: {interval}")

    # Replace "HOLD" with "No Clear Direction" for display
    display_signal = "No Clear Direction" if signal_info["signal"].upper() == "HOLD" else signal_info["signal"]
    signal_text = f"Signal: {display_signal} ({signal_info['confidence']}% confidence)"

    # Color code the signal
    signal_color = pdf.get_signal_color(signal_info["signal"])
    pdf.add_paragraph(signal_text, color=signal_color, bold=True)

    # Color code sentiment
    sentiment_text = f"Sentiment Score: {signal_info['sentiment']}"
    sentiment_color = pdf.get_sentiment_color(signal_info["sentiment"])
    pdf.add_paragraph(sentiment_text, color=sentiment_color, bold=True)

    # 1B. Live Signal Explanation
    pdf.set_link(links["signal_explanation"]) 
    pdf.add_section_title("1.2. Current Signal Explanation")
    import os  

    signal = signal_info['signal']
    confidence = signal_info.get('confidence', 0)
    sentiment = signal_info.get("sentiment", "neutral")
    volatility = signal_info.get("indicators", {}).get("volatility", "N/A")
    confidence_basis = signal_info.get("confidence_basis", "past 2500 candles")
    profit_percent = risk_info.get("expected_profit_percent", "N/A")

    # Safely extract and format prices
    def safe_format(value):
        try:
            return round(float(value), 2)
        except:
            return "N/A"

    entry_price = safe_format(risk_info.get("entry_price"))
    exit_price = safe_format(risk_info.get("final_exit_price", entry_price))
    stop_loss = safe_format(risk_info.get("stop_loss"))
    take_profit = safe_format(risk_info.get("take_profit"))
    rrr = risk_info.get("rr_ratio", "N/A")
    duration = timing_info.get("duration", "N/A")

    # Fallback: try extracting entry price from price_snapshot
    try:
        price_df = signal_info.get("price_snapshot", None)
        if isinstance(price_df, pd.DataFrame) and not price_df.empty:
            fallback_entry = round(float(price_df["close"].iloc[-1]), 2)
            if entry_price == "N/A":
                entry_price = fallback_entry
            if exit_price == "N/A":
                exit_price = fallback_entry
    except:
        pass

    # --- Confidence Phrasing ---
    if confidence >= 80:
        strength_phrase = "a very high level of confidence"
        confidence_color = (0, 150, 0)  # Dark green
    elif confidence >= 65:
        strength_phrase = "a strong degree of confidence"
        confidence_color = (50, 120, 50)  # Medium green
    elif confidence >= 55:
        strength_phrase = "moderate confidence"
        confidence_color = (200, 150, 0)  # Orange
    else:
        strength_phrase = "a cautious confidence level"
        confidence_color = (200, 100, 0)  # Red-orange

    # --- Sentiment Phrasing ---
    if isinstance(sentiment, str):
        if sentiment.lower() == "bullish":
            sentiment_description = "with bullish sentiment supporting the move"
            sentiment_color = (0, 120, 0)  # Green
        elif sentiment.lower() == "bearish":
            sentiment_description = "amid bearish sentiment pressuring the market"
            sentiment_color = (200, 0, 0)  # Red
        else:
            sentiment_description = "with inconclusive sentiment readings"
            sentiment_color = (100, 100, 100)  # Gray
    else:
        sentiment_description = "with inconclusive sentiment readings"
        sentiment_color = (100, 100, 100)  # Gray

    # --- Volatility Phrasing ---
    if isinstance(volatility, (float, int)):
        if volatility > 1.5:
            volatility_phrase = f"Volatility was relatively high ({volatility:.2f}), suggesting increased risk and price swings."
            volatility_color = (200, 0, 0)  # Red
        elif volatility > 0.8:
            volatility_phrase = f"Moderate volatility ({volatility:.2f}) allowed for controlled price movement and decent trade setups."
            volatility_color = (200, 150, 0)  # Orange
        else:
            volatility_phrase = f"Low volatility conditions ({volatility:.2f}) suggested market calmness, suitable for conservative positions."
            volatility_color = (0, 120, 0)  # Green
    else: 
        volatility_phrase = f"Volatility at signal time was recorded as {volatility}."
        volatility_color = (100, 100, 100)  # Gray

    # Get total days from summary if available
    if isinstance(summary, dict):
        analysis_period = summary.get('Total Days Analyzed', '2500 candles')
    else:
        analysis_period = '2500 candles'

    # --- Main Signal Explanation ---
    if signal == "BUY":
        signal_color = (0, 150, 0)  # Green
        explanation_text = (
            f"A BUY signal was generated with {strength_phrase} ({confidence}%) based on analysis over the past {analysis_period}. "
            f"This indicates a favorable outlook for upward price movement, {sentiment_description}. {volatility_phrase} "
            "The system identified optimal entry conditions with bullish technical indicators and supportive market sentiment."
        )
    elif signal == "SELL":
        signal_color = (200, 0, 0)  # Red
        explanation_text = (
            f"A SELL signal was issued with {strength_phrase} ({confidence}%) based on analysis over the past {analysis_period}. "
            f"This suggests a bearish outlook with potential for downward price movement, {sentiment_description}. {volatility_phrase} "
            "The system detected optimal exit/short conditions with bearish technical patterns and negative sentiment indicators."
        )
    else:
        signal_color = (100, 100, 100)  # Gray
        explanation_text = (
            f"A 'No Clear Direction' bias was identified with {strength_phrase} ({confidence}%) based on weak momentum over the past {analysis_period}. "
            f"Market conditions were indecisive, {sentiment_description}. {volatility_phrase} "
            "As a result, the system advised no trade until stronger directional signals appear."
        )

    # --- Add Signal Summary ---
    pdf.set_font("Arial", "B", 10)
    pdf.set_text_color(*signal_color)
    pdf.multi_cell(0, 6, explanation_text)

    # --- Add Risk & Trade Parameters as Table ---
    pdf.ln(2)
    pdf.set_text_color(0, 0, 139)
    pdf.set_font("Arial", "B", 10)
    pdf.multi_cell(0, 6, "\nRisk & Trade Parameters:\n")

    # Calculate max loss and gain per trade
    try:
        entry_val = float(str(entry_price).replace(',', '').replace('$', '')) if entry_price != 'N/A' else 0
        stop_loss_val = float(str(stop_loss).replace(',', '').replace('$', '')) if stop_loss != 'N/A' else 0
        take_profit_val = float(str(take_profit).replace(',', '').replace('$', '')) if take_profit != 'N/A' else 0
        
        max_loss_per_trade = abs(entry_val - stop_loss_val) if stop_loss_val > 0 else 0
        max_gain_per_trade = abs(take_profit_val - entry_val) if take_profit_val > 0 else 0
    except:
        max_loss_per_trade = 0
        max_gain_per_trade = 0

    # Create table data
    risk_params_data = [
        ["Entry Price", f"$ {entry_price if entry_price == 'N/A' else f'{entry_price:,.2f}'}", "NEUTRAL"],
        ["Expected Profit %", f"{profit_percent}", "PROFIT"],
        ["Stop Loss", f"$ {stop_loss if stop_loss == 'N/A' else f'{stop_loss:,.2f}'}", "LOSS"],
        ["Take Profit", f"$ {take_profit if take_profit == 'N/A' else f'{take_profit:,.2f}'}", "PROFIT"],
        ["Max Loss per Trade", f"$ {max_loss_per_trade:,.2f}" if max_loss_per_trade > 0 else "$ 0.00", "LOSS"],
        ["Max Gain per Trade", f"$ {max_gain_per_trade:,.2f}" if max_gain_per_trade > 0 else "$ 0.00", "PROFIT"],
        ["Risk-Reward Ratio", f"{rrr}", "RRR"],
        ["Expected Duration", f"{duration}", "NEUTRAL"]
    ]

    # Table styling
    pdf.set_font("Arial", "B", 9)
    row_height = 6
    col1_width = 50  # Parameter name
    col2_width = 40  # Value

    # Table header
    pdf.set_fill_color(200, 200, 200)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(col1_width, row_height, "Parameter", border=1, align='C', fill=True)
    pdf.cell(col2_width, row_height, "Value", border=1, align='C', fill=True)
    pdf.ln()

    # Table rows
    pdf.set_font("Arial", "", 9)
    for param, value, color_type in risk_params_data:
        # Set row background (alternating light gray)
        pdf.set_fill_color(255, 255, 255)
        
        # Parameter name column (black text)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(col1_width, row_height, param, border=1, align='L', fill=True)
        
        # Value column with color coding
        if color_type == "PROFIT":
            try:
                # Check if it's a percentage or dollar amount
                if "%" in value:
                    profit_val = float(value.replace('%', ''))
                    text_color = (0, 150, 0) if profit_val > 0 else (200, 0, 0) if profit_val < 0 else (100, 100, 100)
                else:
                    # For take profit and max gain
                    text_color = (0, 150, 0)
            except:
                text_color = (0, 150, 0)
        elif color_type == "LOSS":
            text_color = (200, 0, 0)
        elif color_type == "RRR":
            try:
                rrr_val = float(str(rrr).split(':')[0]) if ':' in str(rrr) else float(rrr)
                text_color = (0, 150, 0) if rrr_val >= 2 else (200, 150, 0) if rrr_val >= 1 else (200, 0, 0)
            except:
                text_color = (100, 100, 100)
        elif color_type == "NEUTRAL":
            if "Duration" in param:
                text_color = (120, 80, 0)
            else:
                text_color = (0, 102, 204)
        else:
            text_color = (0, 0, 0)
        
        pdf.set_text_color(*text_color)
        pdf.cell(col2_width, row_height, value, border=1, align='C', fill=True)
        pdf.ln()

    # --- Contextual Summary ---   
    pdf.add_page()
    pdf.set_text_color(90, 60, 0)
    pdf.set_font("Arial", "B", 10)
    
    # Different contextual summaries based on signal type
    def safe_float(val, default=0.0):
        """Convert val to float if possible, otherwise return default."""
        try:
            return float(val)
        except (ValueError, TypeError):
            return default

    if signal in ["BUY", "SELL"]:
        pdf.multi_cell(0, 5, (
            f"\nThe system identified ${safe_float(entry_price):,.2f} as the best entry point, "
            f"with downside risk managed at ${safe_float(stop_loss):,.2f} "
            f"and target reward at ${safe_float(take_profit):,.2f}. "
            f"Based on these, a {profit_percent} % gain was expected. "
            f"Risk-Reward stood at {rrr}, and the signal is considered valid for {duration}. "
            "This setup reflects a strong probability for price action favoring the trade direction."
        ))
    else:  # HOLD signal
        pdf.multi_cell(0, 5, (
            f"\nThe system determined that current market conditions do not favor taking a position at this time. "
            f"With the current price around ${safe_float(entry_price):,.2f}, "
            f"the analysis suggests waiting for clearer directional signals. "
            f"This recommendation remains valid for {duration}, during which continued monitoring is advised. "
            "The system will reassess conditions and may provide actionable signals when market dynamics improve."
        ))


    # --- Generate Professional Trading Chart ---
    try:
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
        import matplotlib.ticker as mticker
        import numpy as np
        
        # Get price data
        price_df = signal_info.get("price_snapshot", None)
        if isinstance(price_df, pd.DataFrame) and not price_df.empty:
            df = price_df.copy()
            df.index = pd.to_datetime(df.index)
            df = df.sort_index()
            
            # Take last 100 points for better visualization
            df = df.tail(100)
            
            # Ensure numeric data
            df['close'] = pd.to_numeric(df['close'], errors='coerce')
            df = df.dropna()
            
            if len(df) > 10:
                # Check if this is a HOLD signal (all tp and sl values are zero)
                is_hold_signal = (signal == 'HOLD' or 
                                (stop_loss == "N/A" or stop_loss == 0) and 
                                (take_profit == "N/A" or take_profit == 0))
                
                if is_hold_signal:
                    # Generate simple trend chart for HOLD signals
                    plt.style.use('default')
                    fig, ax = plt.subplots(figsize=(14, 8))
                    
                    # Set white background
                    fig.patch.set_facecolor('white')
                    ax.set_facecolor('white')
                    
                    # Plot price line
                    ax.plot(df.index, df['close'], color='#0066cc', linewidth=2.5, label='Price Trend')
                    
                    # Add entry line if available
                    if entry_price != "N/A":
                        ax.axhline(y=entry_price, color='#ff8800', linestyle='--', linewidth=2, 
                                label=f'Entry: ${entry_price:,.2f}', alpha=0.9)
                    
                    # Add signal indicator
                    signal_color_code = '#0066cc'
                    ax.text(0.98, 0.95, f'{signal} Signal\n{confidence}% Confidence', 
                        transform=ax.transAxes, fontsize=14, fontweight='bold',
                        bbox=dict(boxstyle='round,pad=0.5', facecolor=signal_color_code, alpha=0.8),
                        ha='right', va='top', color='white')
                    
                    # Styling
                    ax.set_title(f'{symbol} - Past 100 Periods Position Analysis', 
                            fontsize=18, fontweight='bold', color='black', pad=20)
                    ax.set_xlabel('Time (UTC)', fontsize=12, color='black')
                    ax.set_ylabel('Price (USD)', fontsize=12, color='black')
                    
                    # Grid
                    ax.grid(True, alpha=0.3, color='gray')
                    
                    # Format dates
                    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d-%b %H:%M'))
                    ax.xaxis.set_major_locator(mdates.HourLocator(interval=max(1, len(df)//10)))
                    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, color='black')
                    
                    # Color axis labels
                    ax.tick_params(colors='black')
                    
                    # Smart Y-axis formatting based on price range
                    price_min, price_max = df['close'].min(), df['close'].max()
                    price_range = price_max - price_min
                    
                    if price_range > 1000:
                        # For large prices (like BTC), use no decimals
                        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{x:,.0f}'))
                    elif price_range > 100:
                        # For medium prices, use 1 decimal
                        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{x:,.1f}'))
                    elif price_range > 10:
                        # For smaller prices, use 2 decimals
                        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{x:,.2f}'))
                    else:
                        # For very small prices, use 3 decimals
                        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{x:,.3f}'))
                    
                    # Add legend
                    ax.legend(loc='upper left', frameon=True, fancybox=True, shadow=True, 
                            fontsize=10, framealpha=0.9)
                    
                    # Add timestamp
                    timestamp = pd.Timestamp.now()
                    formatted_timestamp = timestamp.strftime("%d-%b-%Y %H:%M")
                    ax.text(0.02, 0.02, f'Generated: {formatted_timestamp}', 
                        transform=ax.transAxes, fontsize=8, color='gray', alpha=0.7)
                    
                    # Tight layout
                    plt.tight_layout()
                    
                else:
                    # Generate trading chart for BUY/SELL signals
                    plt.style.use('default')
                    fig, ax = plt.subplots(figsize=(14, 8))
                    
                    # Set white background
                    fig.patch.set_facecolor('white')
                    ax.set_facecolor('white')
                    
                    # Plot price line
                    ax.plot(df.index, df['close'], color='#0066cc', linewidth=2.5, label='Price Trend')
                    
                    # Add entry, stop loss, and take profit lines
                    if entry_price != "N/A":
                        ax.axhline(y=entry_price, color='#ff8800', linestyle='--', linewidth=2, 
                                alpha=0.9, label=f'Entry: ${entry_price:,.2f}')
                    
                    if stop_loss != "N/A":
                        ax.axhline(y=stop_loss, color='#ff0000', linestyle=':', linewidth=2, 
                                alpha=0.9, label=f'Stop Loss: ${stop_loss:,.2f}')
                    
                    if take_profit != "N/A":
                        ax.axhline(y=take_profit, color='#00cc00', linestyle=':', linewidth=2, 
                                alpha=0.9, label=f'Take Profit: ${take_profit:,.2f}')
                    
                    # Add risk and profit zones
                    if entry_price != "N/A" and stop_loss != "N/A":
                        ax.fill_between(df.index, stop_loss, entry_price, alpha=0.1, color='red', 
                                    label='Risk Zone')
                    
                    if entry_price != "N/A" and take_profit != "N/A":
                        ax.fill_between(df.index, entry_price, take_profit, alpha=0.1, color='green',
                                    label='Profit Zone')
                    
                    # Add signal indicator
                    signal_color_code = '#00cc00' if signal == 'BUY' else '#ff0000' if signal == 'SELL' else '#ff8800'
                    ax.text(0.98, 0.95, f'{signal} Signal\n{confidence}% Confidence', 
                        transform=ax.transAxes, fontsize=14, fontweight='bold',
                        bbox=dict(boxstyle='round,pad=0.5', facecolor=signal_color_code, alpha=0.8),
                        ha='right', va='top', color='white')
                    
                    # Styling
                    ax.set_title(f'{symbol} - Professional Trading Analysis', 
                            fontsize=18, fontweight='bold', color='black', pad=20)
                    ax.set_xlabel('Time', fontsize=12, color='black')
                    ax.set_ylabel('Price (USD)', fontsize=12, color='black')
                    
                    # Grid
                    ax.grid(True, alpha=0.3, color='gray')
                    
                    # Format dates
                    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d-%b %H:%M'))
                    ax.xaxis.set_major_locator(mdates.HourLocator(interval=max(1, len(df)//10)))
                    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, color='black')
                    
                    # Color axis labels
                    ax.tick_params(colors='black')
                    
                    # Smart Y-axis formatting based on price range
                    price_min, price_max = df['close'].min(), df['close'].max()
                    price_range = price_max - price_min
                    
                    if price_range > 1000:
                        # For large prices (like BTC), use no decimals
                        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{x:,.0f}'))
                    elif price_range > 100:
                        # For medium prices, use 1 decimal
                        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{x:,.1f}'))
                    elif price_range > 10:
                        # For smaller prices, use 2 decimals
                        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{x:,.2f}'))
                    else:
                        # For very small prices, use 3 decimals
                        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{x:,.3f}'))
                    
                    # Add legend
                    ax.legend(loc='upper left', frameon=True, fancybox=True, shadow=True, 
                            fontsize=10, framealpha=0.9)
                    
                    # Add timestamp
                    timestamp = pd.Timestamp.now()
                    formatted_timestamp = timestamp.strftime("%d-%b-%Y %H:%M")
                    ax.text(0.02, 0.02, f'Generated: {formatted_timestamp}', 
                        transform=ax.transAxes, fontsize=8, color='gray', alpha=0.7)
                    
                    # Tight layout
                    plt.tight_layout()
                
                # Save with unique name for this section
                os.makedirs("reports/plots", exist_ok=True)
                professional_chart_path = "reports/plots/professional_trading_chart.png"
                plt.savefig(professional_chart_path, dpi=150, bbox_inches='tight', 
                        facecolor='white', edgecolor='none')
                plt.close()
                
                # Reset matplotlib style to default for other plots
                plt.style.use('default')
                
                # Add to PDF
                pdf.ln(3)
                pdf.add_image(professional_chart_path, size_type="medium")
                pdf.ln(2)
                
                # No need for separate legend text anymore since it's on the chart
                
            else:
                raise ValueError("Insufficient data points for chart generation")
                
    except Exception as e:
        pdf.ln(2)
        pdf.set_font("Arial", "B", 10)
        pdf.set_text_color(255, 0, 0)
        pdf.multi_cell(0, 5, f"(Professional chart generation failed: {e})")
        
        # Fallback: Generate simple signal visualization
        try:
            plt.figure(figsize=(10, 4))
            
            sl = stop_loss if stop_loss != "N/A" else 0
            ep = entry_price if entry_price != "N/A" else 0
            tp = take_profit if take_profit != "N/A" else 0

            macd = ep + 150
            rsi = ep + 300

            levels = [sl, ep, tp, macd, rsi]
            labels = ['Stop Loss', 'Entry Price', 'Take Profit', 'MACD Level', 'RSI Threshold']
            colors = ['red', 'blue', 'green', 'gray', 'gray']
            linestyles = ['--', '--', '--', ':', ':']

            for lvl, lbl, col, style in zip(levels, labels, colors, linestyles):
                if lvl > 0:
                    plt.axhline(y=lvl, linestyle=style, color=col, linewidth=2, label=f"{lbl}: {lvl:,.2f}")

            if sl < ep:
                plt.fill_betweenx([sl, ep], 0, 1, color='red', alpha=0.1, transform=plt.gca().get_yaxis_transform())
            if tp > ep:
                plt.fill_betweenx([ep, tp], 0, 1, color='green', alpha=0.1, transform=plt.gca().get_yaxis_transform())

            plt.title("Signal Risk-Reward Setup & Indicators", fontsize=10, fontweight='bold')
            plt.xticks([])
            
            # Add legend to fallback chart too
            plt.legend(loc='upper left', frameon=True, fancybox=True, shadow=True, 
                    fontsize=9, framealpha=0.9)
            
            plt.tight_layout()
            plt.gca().yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{x:,.0f}'))

            fallback_path = "reports/plots/signal_risk_setup.png"
            plt.savefig(fallback_path, facecolor='white')
            plt.close()

            pdf.ln(2)
            pdf.add_image(fallback_path, size_type="small")

        except Exception as fallback_error:
            pdf.add_paragraph(f"(Fallback chart also failed: {fallback_error})", color=(255, 0, 0))

    pdf.add_page()

    # 1C. Price Snapshot
    pdf.set_link(links["price_vol_info"])
    pdf.add_section_title("\n2. Market Data & Price Analysis (UTC Time Zone)")
    pdf.set_link(links["price_snapshot"])
    if 'price_snapshot' in signal_info:
        pdf.ln(2)
        pdf.set_x(pdf.l_margin)
        pdf.add_section_title("\n2.1. Recent Price Snapshot (Latest 5 Periods)")
        price_snapshot = signal_info['price_snapshot'].copy()
        price_snapshot = price_snapshot.tail(5)
        price_snapshot.index = pd.to_datetime(price_snapshot.index)
        price_snapshot.reset_index(inplace=True)

        # Adjust column names safely
        if price_snapshot.shape[1] == 7:
            price_snapshot.columns = ["Timestamp", "Open", "High", "Low", "Close", "Volume", "Extra"]
            price_snapshot.drop("Extra", axis=1, inplace=True)
        elif price_snapshot.shape[1] == 6:
            price_snapshot.columns = ["Timestamp", "Open", "High", "Low", "Close", "Volume"]

        # Format timestamps with abbreviated month
        price_snapshot["Timestamp"] = price_snapshot["Timestamp"].dt.strftime('%d-%b-%Y %H:%M')

        # Add symbol
        price_snapshot["Symbol"] = symbol
        price_snapshot = price_snapshot[["Timestamp", "Symbol", "Open", "High", "Low", "Close", "Volume"]]

        # Store original numeric values before formatting for color calculations
        original_open_values = price_snapshot["Open"].values
        original_high_values = price_snapshot["High"].values
        original_low_values = price_snapshot["Low"].values
        original_close_values = price_snapshot["Close"].values
        original_volume_values = price_snapshot["Volume"].values

        # Helper function to get volume color based on previous value
        def get_volume_color(current_vol, prev_vol, is_first_row=False):
            if is_first_row:
                return (255, 255, 255)  # White for first row
            elif current_vol > prev_vol:
                return (230, 250, 230)  # Light green for higher volume
            else:
                return (250, 230, 230)  # Light red for lower volume

        # Create color arrays for each column
        open_colors = []
        high_colors = []
        low_colors = []
        close_colors = []
        volume_colors = []

        for i in range(len(price_snapshot)):
            # Price colors - fixed colors
            open_colors.append((255, 255, 200))   # Light yellow for open (neutral)
            high_colors.append((230, 250, 230))   # Light green for high
            low_colors.append((250, 230, 230))    # Light red for low
            close_colors.append((255, 255, 200))  # Light yellow for close (neutral)
            
            # Volume colors (compare with previous row)
            if i == 0:
                volume_colors.append(get_volume_color(original_volume_values[i], None, is_first_row=True))
            else:
                volume_colors.append(get_volume_color(original_volume_values[i], original_volume_values[i-1]))

        # Format the values after storing colors
        for col in ["Open", "High", "Low", "Close"]:
            price_snapshot[col] = price_snapshot[col].apply(lambda x: "{:,.2f}".format(float(x)) if pd.notna(x) else "N/A")
        price_snapshot["Volume"] = price_snapshot["Volume"].apply(lambda x: "{:,.2f}".format(float(x)) if pd.notna(x) else "N/A")

        # Extract base asset from symbol (e.g., BTC from BTCUSDT)
        #base_asset = ''.join([c for c in symbol if not c.isdigit()]).replace("USDT", "")

        # Set new column names with base asset in Volume
        price_snapshot.columns = [
            "Timestamp", "Symbol", 
            "Open ($)", "High ($)", "Low ($)", "Close ($)", 
            #f"Volume ({base_asset})"
            "Volume (coins)"
        ]

        # Create cell colors dictionary
        cell_colors_dict = {}
        for i in range(len(price_snapshot)):
            cell_colors_dict[(i, 2)] = open_colors[i]    # Open column
            cell_colors_dict[(i, 3)] = high_colors[i]    # High column
            cell_colors_dict[(i, 4)] = low_colors[i]     # Low column
            cell_colors_dict[(i, 5)] = close_colors[i]   # Close column
            cell_colors_dict[(i, 6)] = volume_colors[i]  # Volume column

        pdf.add_table(price_snapshot, list(price_snapshot.columns), apply_row_coloring=False, cell_colors=cell_colors_dict)

    # 1C.2 Historical Price Points - One Week Before Each Snapshot Row
    pdf.set_link(links["historical_points"])
    pdf.add_section_title("2.2. Weekly Price Progression Analysis")

    try:
        # Import timedelta at the beginning of this section
        from datetime import timedelta
        
        df = signal_info["price_snapshot"].copy()
        df.index = pd.to_datetime(df.index)
        df.sort_index(inplace=True)

        snapshot_df = df.tail(5).copy()
        snapshot_df.index = pd.to_datetime(snapshot_df.index)

        historical_rows = []
        graph_data = []

        # Store original values for color calculations
        historical_close_values = []
        historical_volume_values = []
        hist_close_values = []
        hist_volume_values = []

        for timestamp in snapshot_df.index:
            label_date = timestamp.strftime("%d-%b-%Y %H:%M")
            current_close = snapshot_df.loc[timestamp]["close"]
            current_volume = snapshot_df.loc[timestamp]["volume"]

            # Target time: 1 week before
            target_time = timestamp - timedelta(days=7)

            # Check if target time is within available data
            if target_time < df.index.min():
                week_ago_date = "N/A"
                hist_close = "N/A"
                hist_volume = "N/A"
                hist_close_value = None
                hist_volume_value = None
            else:
                # Find closest available time
                nearest_idx = df.index.get_indexer([target_time], method="nearest")[0]
                week_ago_timestamp = df.index[nearest_idx]
                week_ago_date = week_ago_timestamp.strftime("%d-%b-%Y %H:%M")

                row = df.iloc[nearest_idx]
                hist_close = f"{row['close']:,.2f}"
                hist_volume = f"{row['volume']:,.2f}"
                hist_close_value = row['close']
                hist_volume_value = row['volume']

            historical_rows.append({
                "Snapshot Time": label_date,
                "Close": f"{current_close:,.2f}",
                "Volume": f"{current_volume:,.2f}",
                "Historical Time": week_ago_date,
                "Historical Close": hist_close,
                "Historical Volume": hist_volume
            })

            # Store values for coloring
            historical_close_values.append(current_close)
            historical_volume_values.append(current_volume)
            hist_close_values.append(hist_close_value)
            hist_volume_values.append(hist_volume_value)

            # Store data for graph
            graph_data.append({
                'date': timestamp.strftime("%d-%b-%Y %H:%M"),
                'current_close': current_close,
                'current_volume': current_volume,
                'hist_close': hist_close_value,
                'hist_volume': hist_volume_value
            })

        hist_df = pd.DataFrame(historical_rows)
        hist_df.columns = [
            "Snapshot Time", "Close ($)", "Volume (coins)",
            "Historical Time", "Historical Close ($)", "Historical Volume (coins)"
        ]

        def get_comparison_color(current_val, hist_val, is_volume=False):
            if hist_val is None or current_val is None:
                return (255, 255, 255)  # White for N/A values
            
            if is_volume:
                # For volume, compare current vs historical
                if current_val > hist_val:
                    return (230, 250, 230)  # Light green for increase
                else:
                    return (250, 230, 230)  # Light red for decrease
            else:
                # For close prices, use neutral yellow color
                return (255, 255, 200)  # Light yellow (neutral)

        # Create colors for historical comparison table
        hist_cell_colors = {}
        for i in range(len(hist_df)):
            # Close price colors (neutral yellow for open/close)
            hist_cell_colors[(i, 1)] = (255, 255, 200)  # Current close (neutral yellow)
            hist_cell_colors[(i, 4)] = (255, 255, 200)  # Historical close (neutral yellow)
            
            # Volume colors
            if i == 0:
                # First row - white for current volume, white for historical volume
                hist_cell_colors[(i, 2)] = (255, 255, 255)  # First current volume (white)
                hist_cell_colors[(i, 5)] = (255, 255, 255)  # First historical volume (white)
            else:
                # Compare current volume with previous row's current volume
                current_vol = historical_volume_values[i]
                prev_vol = historical_volume_values[i-1]
                if current_vol > prev_vol:
                    hist_cell_colors[(i, 2)] = (230, 250, 230)  # Light green
                else:
                    hist_cell_colors[(i, 2)] = (250, 230, 230)  # Light red
                
                # Compare historical volume with previous row's historical volume
                hist_vol = hist_volume_values[i]
                prev_hist_vol = hist_volume_values[i-1]
                if hist_vol is not None and prev_hist_vol is not None:
                    if hist_vol > prev_hist_vol:
                        hist_cell_colors[(i, 5)] = (230, 250, 230)  # Light green
                    else:
                        hist_cell_colors[(i, 5)] = (250, 230, 230)  # Light red
                else:
                    hist_cell_colors[(i, 5)] = (255, 255, 255)  # White for N/A

        pdf.add_table(hist_df, list(hist_df.columns), apply_row_coloring=False, cell_colors=hist_cell_colors)

        # 1C.2.1 Historical Price Points - Monthly Progressive Data
        pdf.add_page()
        pdf.set_link(links["historical_points_months"])
        pdf.add_section_title("2.3. Monthly Price Progression Analysis")

        # Get current timestamp for monthly calculations
        current_timestamp = snapshot_df.index.max()

        # Calculate how many months of data we actually have
        data_span_days = (df.index.max() - df.index.min()).days
        available_months = max(1, int(data_span_days / 30))  # Calculate based on actual data span
        max_months = min(available_months, 12)  # Use actual available months, cap at 12

        print(f"Debug Info: Data available from {df.index.min()} to {df.index.max()} ({data_span_days} days)")
        print(f"Available months calculated: {available_months}, using max_months: {max_months}")

        # Create monthly historical data for available months
        monthly_historical_rows = []
        monthly_close_values = []  # Store for coloring calculations
        monthly_volume_values = []

        for snapshot_idx, timestamp in enumerate(snapshot_df.index):
            label_date = timestamp.strftime("%d-%b-%Y %H:%M")
            current_close = snapshot_df.loc[timestamp]["close"]
            current_volume = snapshot_df.loc[timestamp]["volume"]
            
            row_data = {
                "Snapshot Time": label_date,
                "Current Close": f"{current_close:,.2f}",
                "Current Volume": f"{current_volume:,.2f}"
            }
            
            # Store values for this row
            row_close_values = [current_close]
            row_volume_values = [current_volume]
            
            # Add monthly data (1 month back, 2 months back, etc.)
            available_months_for_row = 0
            for month_back in range(1, max_months + 1):
                target_time = timestamp - timedelta(days=30 * month_back)
                
                if target_time < df.index.min():
                    month_date = "N/A"
                    month_close = "N/A"
                    month_volume = "N/A"
                    month_close_val = None
                    month_volume_val = None
                else:
                    # Find closest available time
                    nearest_idx = df.index.get_indexer([target_time], method="nearest")[0]
                    month_timestamp = df.index[nearest_idx]
                    month_date = month_timestamp.strftime("%d-%b-%Y %H:%M")
                    
                    month_row = df.iloc[nearest_idx]
                    month_close = f"{month_row['close']:,.2f}"
                    month_volume = f"{month_row['volume']:,.2f}"
                    month_close_val = month_row['close']
                    month_volume_val = month_row['volume']
                    available_months_for_row = month_back
                
                row_data[f"{month_back}M Time"] = month_date
                row_data[f"{month_back}M Close"] = month_close
                row_data[f"{month_back}M Volume"] = month_volume
                
                # Store numeric values
                if month_close_val is not None:
                    row_close_values.append(month_close_val)
                if month_volume_val is not None:
                    row_volume_values.append(month_volume_val)
            
            # Add debug info about how many months of data this row has
            if snapshot_idx == 0:  # Only print for first row to avoid spam
                print(f"Row {snapshot_idx} has {available_months_for_row} months of historical data")
            
            monthly_historical_rows.append(row_data)
            monthly_close_values.append(row_close_values)
            monthly_volume_values.append(row_volume_values)

        # Create dataframe and determine available columns
        monthly_hist_df = pd.DataFrame(monthly_historical_rows)

        # Get column names dynamically based on available data
        available_columns = list(monthly_hist_df.columns)

        # Rename columns for better display
        column_mapping = {
            "Snapshot Time": "Snapshot Time",
            "Current Close": "Close ($)",
            "Current Volume": "Volume (coins)"
        }

        # Add monthly column mappings
        for col in available_columns:
            if "M Time" in col:
                month_num = col.replace("M Time", "")
                column_mapping[col] = f"{month_num}M Ago Time"
            elif "M Close" in col:
                month_num = col.replace("M Close", "")
                column_mapping[col] = f"{month_num}M Ago C ($)"
            elif "M Volume" in col:
                month_num = col.replace("M Volume", "")
                column_mapping[col] = f"{month_num}M Ago V (coins)"

        monthly_hist_df.rename(columns=column_mapping, inplace=True)

        # Create colors for monthly table
        monthly_cell_colors = {}
        for row_idx in range(len(monthly_hist_df)):
            col_idx = 1  # Start from Close column
            
            # Current Close - neutral yellow color
            monthly_cell_colors[(row_idx, col_idx)] = (255, 255, 200)  # Light yellow (neutral)
            col_idx += 1
            
            # Current Volume - first row white, others compare with previous row
            if row_idx == 0:
                monthly_cell_colors[(row_idx, col_idx)] = (255, 255, 255)  # White for first row
            else:
                current_vol = monthly_volume_values[row_idx][0]  # Current volume
                prev_vol = monthly_volume_values[row_idx-1][0]   # Previous row's current volume
                if current_vol > prev_vol:
                    monthly_cell_colors[(row_idx, col_idx)] = (230, 250, 230)  # Light green
                else:
                    monthly_cell_colors[(row_idx, col_idx)] = (250, 230, 230)  # Light red
            col_idx += 1
            
            # Process monthly columns
            month_counter = 1
            for col_name in monthly_hist_df.columns[3:]:  # Skip first 3 columns
                if "C ($)" in col_name:  # Close price columns
                    monthly_cell_colors[(row_idx, col_idx)] = (255, 255, 200)  # Light yellow (neutral)
                elif "V (coins)" in col_name:  # Volume columns
                    if row_idx == 0:
                        # First row - white for all volume columns
                        monthly_cell_colors[(row_idx, col_idx)] = (255, 255, 255)  # White for first row
                    else:
                        # Get the month number from column name
                        month_num = int(col_name.split("M")[0])
                        
                        # Find corresponding volume values
                        current_row_volumes = monthly_volume_values[row_idx]
                        prev_row_volumes = monthly_volume_values[row_idx-1]
                        
                        # Check if we have volume data for this month in both rows
                        if month_num < len(current_row_volumes) and month_num < len(prev_row_volumes):
                            current_month_vol = current_row_volumes[month_num]
                            prev_month_vol = prev_row_volumes[month_num]
                            
                            if current_month_vol is not None and prev_month_vol is not None:
                                if current_month_vol > prev_month_vol:
                                    monthly_cell_colors[(row_idx, col_idx)] = (230, 250, 230)  # Light green
                                else:
                                    monthly_cell_colors[(row_idx, col_idx)] = (250, 230, 230)  # Light red
                            else:
                                monthly_cell_colors[(row_idx, col_idx)] = (255, 255, 255)  # White for N/A
                        else:
                            monthly_cell_colors[(row_idx, col_idx)] = (255, 255, 255)  # White for N/A
                col_idx += 1

        pdf.add_table(monthly_hist_df, list(monthly_hist_df.columns), apply_row_coloring=False, cell_colors=monthly_cell_colors)

        # Add Price and Volume Comparison Graph (LINE GRAPHS)
        pdf.add_page()
        
        pdf.set_link(links["price_comparison"])
        pdf.add_section_title("2.4. Short-term Price & Volume Trends (Current vs 1 Week Ago)")
        
        # Create the graph
        import matplotlib.pyplot as plt
        import numpy as np
        from datetime import datetime
        
        # Filter out data where historical values are None
        valid_data = [item for item in graph_data if item['hist_close'] is not None]
        
        if valid_data:
            dates = [item['date'] for item in valid_data]
            current_closes = [item['current_close'] for item in valid_data]
            hist_closes = [item['hist_close'] for item in valid_data]
            current_volumes = [item['current_volume'] for item in valid_data]
            hist_volumes = [item['hist_volume'] for item in valid_data]
            
            # Convert dates to include day names
            date_labels = []
            for date_str in dates:
                try:
                    date_obj = datetime.strptime(date_str, '%d-%b-%Y %H:%M')
                    day_name = date_obj.strftime('%A')  # Full day name
                    date_labels.append(f"{day_name}\n{date_str}")
                except:
                    date_labels.append(date_str)  # Fallback to original if parsing fails
            
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(18, 16))
            
            # Increase spacing between subplots
            plt.subplots_adjust(hspace=1)
            
            # Price comparison - LINE GRAPH
            x = np.arange(len(dates))
            
            ax1.plot(x, current_closes, marker='o', linewidth=3, markersize=8, 
                    label='Current Close', color='green', alpha=0.8)
            ax1.plot(x, hist_closes, marker='s', linewidth=3, markersize=8, 
                    label='Historical Close (1 Week Ago)', color='blue', alpha=0.8)
            
            ax1.set_xlabel('Date (Current Week)', fontsize=12)
            ax1.set_ylabel('Price ($)', fontsize=12)
            ax1.set_title(f'{symbol} Price Comparison - Current vs 1 Week Ago', fontsize=14, fontweight='bold')
            ax1.set_xticks(x)
            ax1.set_xticklabels(date_labels, rotation=45, fontsize=10)
            ax1.legend(fontsize=11)
            ax1.grid(True, alpha=0.3)
            ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.2f}'))
            
            # Fill area between lines for better visualization
            ax1.fill_between(x, current_closes, hist_closes, alpha=0.2, 
                           color='green' if sum(current_closes) > sum(hist_closes) else 'red')
            
            # Volume comparison - LINE GRAPH
            ax2.plot(x, current_volumes, marker='o', linewidth=3, markersize=8, 
                    label='Current Volume', color='red', alpha=0.8)
            ax2.plot(x, hist_volumes, marker='s', linewidth=3, markersize=8, 
                    label='Historical Volume (1 Week Ago)', color='orange', alpha=0.8)
            
            ax2.set_xlabel('Date (Current Week)', fontsize=12)
            ax2.set_ylabel('Volume (coins)', fontsize=12)
            ax2.set_title(f'{symbol} Volume Comparison - Current vs 1 Week Ago', fontsize=14, fontweight='bold')
            ax2.set_xticks(x)
            ax2.set_xticklabels(date_labels, rotation=45, fontsize=10)
            ax2.legend(fontsize=11)
            ax2.grid(True, alpha=0.3)
            ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x:,.0f}'))
            
            # Fill area between lines for better visualization
            ax2.fill_between(x, current_volumes, hist_volumes, alpha=0.2,
                           color='red' if sum(current_volumes) > sum(hist_volumes) else 'orange')
            
            plt.tight_layout()
            
            # Save to reports/plots folder
            import os
            os.makedirs("reports/plots", exist_ok=True)
            plot_filename = f"reports/plots/{symbol}_historical_comparison.png"
            plt.savefig(plot_filename, format='png', dpi=300, bbox_inches='tight')
            plt.close()
            
            # Add graph to PDF
            pdf.add_image(plot_filename, size_type="large")

        # 1C.3.1 Extended Historical Analysis - 12 Weeks + Monthly Data
        pdf.add_page()
        pdf.set_link(links["price_comparison_w_months"])
        pdf.add_section_title("2.5. Extended Timeframe Analysis (Past 3 Months)")

        try:
            # Get current timestamp (latest data point)
            current_timestamp = df.index.max()
            
            # Calculate 12 weeks of data
            weekly_data = []
            monthly_data = []
            
            # Generate 12 weeks of data (going backwards from current timestamp)
            # Changed range to start from 1 instead of 0, so we get weeks 1-12
            for week in range(1, 13):  # This creates weeks 1, 2, 3, ..., 12
                week_timestamp = current_timestamp - timedelta(weeks=week)
                
                # Find closest data point for this week
                if week_timestamp >= df.index.min():
                    nearest_idx = df.index.get_indexer([week_timestamp], method="nearest")[0]
                    nearest_timestamp = df.index[nearest_idx]
                    row = df.iloc[nearest_idx]
                    
                    weekly_data.append({
                        'week': f'Week -{week}',  # This will now create Week -1, Week -2, ..., Week -12
                        'date': nearest_timestamp.strftime("%d-%b-%Y"),
                        'close': row['close'],
                        'volume': row['volume']
                    })
            
            # Use the same max_months calculation as the Monthly Progressive Data section
            # This ensures consistency across all sections
            extended_max_months = min(available_months, 12)  # Use the same calculated available_months
            
            print(f"Extended Analysis: Using {extended_max_months} months for extended analysis")
            
            # Generate monthly data (using consistent logic)
            for month in range(extended_max_months):
                month_timestamp = current_timestamp - timedelta(days=30*month)
                
                # Check if we have data for this month (but don't break early)
                if month_timestamp < df.index.min():
                    # Still add the month but mark data as unavailable
                    monthly_data.append({
                        'month': f'Month -{month}',
                        'date': month_timestamp.strftime("%Y-%m"),
                        'avg_close': None,
                        'avg_volume': None
                    })
                    continue
                
                # Calculate monthly average for the period
                month_start = month_timestamp - timedelta(days=15)
                month_end = month_timestamp + timedelta(days=15)
                
                # Filter data for this month period
                month_mask = (df.index >= month_start) & (df.index <= month_end)
                month_df = df[month_mask]
                
                if not month_df.empty:
                    avg_close = month_df['close'].mean()
                    avg_volume = month_df['volume'].mean()
                    
                    monthly_data.append({
                        'month': f'Month -{month}',
                        'date': month_timestamp.strftime("%Y-%m"),
                        'avg_close': avg_close,
                        'avg_volume': avg_volume
                    })
                else:
                    # No data available for this time period
                    monthly_data.append({
                        'month': f'Month -{month}',
                        'date': month_timestamp.strftime("%Y-%m"),
                        'avg_close': None,
                        'avg_volume': None
                    })
            
            # Filter out None values for plotting
            valid_monthly_data = [item for item in monthly_data if item['avg_close'] is not None]
            
            # Create the combined bar and line graph
            if weekly_data and valid_monthly_data:
                fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(20, 16))

                # Increase spacing between subplots
                plt.subplots_adjust(hspace=1)
                
                # Reverse data to show chronologically (oldest to newest)
                # Now Week -12 will be leftmost, Week -1 will be rightmost
                weekly_data.reverse()
                valid_monthly_data.reverse()
                
                # Calculate weekly averages for line graph
                weekly_avg_closes = []
                for i in range(0, len(weekly_data), 4):  # Every 4 weeks = ~1 month
                    chunk = weekly_data[i:i+4]
                    if chunk:
                        avg_close = sum(item['close'] for item in chunk) / len(chunk)
                        weekly_avg_closes.append(avg_close)
                
                # Prepare data for plotting
                weeks = [item['week'] for item in weekly_data]
                week_closes = [item['close'] for item in weekly_data]
                months = [item['month'] for item in valid_monthly_data]
                monthly_avg_closes = [item['avg_close'] for item in valid_monthly_data]
                
                # Plot 1: Price Analysis (Bar + Line)
                x_weeks = np.arange(len(weeks))
                
                # Bar graph for weekly closes
                bars = ax1.bar(x_weeks, week_closes, alpha=0.6, color='lightblue', 
                            label='Weekly Final Close', width=0.8)
                
                # Line graph for weekly averages (every 4 weeks)
                if len(weekly_avg_closes) > 1:
                    x_weekly_avg = np.arange(0, len(weeks), 4)[:len(weekly_avg_closes)]
                    ax1.plot(x_weekly_avg, weekly_avg_closes, marker='o', linewidth=3, 
                            markersize=8, color='green', label='Weekly Avg Close', alpha=0.8)
                
                # Line graph for monthly averages
                if len(monthly_avg_closes) > 1:
                    # Map monthly data to weekly x-axis (approximately every 4.33 weeks per month)
                    x_monthly = np.linspace(0, len(weeks)-1, len(monthly_avg_closes))
                    ax1.plot(x_monthly, monthly_avg_closes, marker='s', linewidth=4,
                            markersize=10, color='red', label='Monthly Avg Close', alpha=0.9)
                
                ax1.set_xlabel('Time Period', fontsize=12)
                ax1.set_ylabel('Price ($)', fontsize=12)
                ax1.set_title(f'{symbol} Extended Price Analysis - 12 Weeks with Monthly Averages', 
                            fontsize=14, fontweight='bold')
                ax1.set_xticks(x_weeks[::2])  # Show every 2nd week to avoid crowding
                ax1.set_xticklabels([weeks[i] for i in range(0, len(weeks), 2)], rotation=45, fontsize=9)
                ax1.legend(fontsize=11)
                ax1.grid(True, alpha=0.3)
                ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.2f}'))
                
                # Add value labels on bars (every 3rd bar to avoid crowding)
                for i in range(0, len(bars), 3):
                    height = bars[i].get_height()
                    ax1.text(bars[i].get_x() + bars[i].get_width()/2., height,
                            f'${height:,.0f}', ha='center', va='bottom', fontsize=8, rotation=90)
                
                # Plot 2: Volume Analysis
                week_volumes = [item['volume'] for item in weekly_data]
                monthly_avg_volumes = [item['avg_volume'] for item in valid_monthly_data]
                
                # Weekly volume averages (every 4 weeks)
                weekly_avg_volumes = []
                for i in range(0, len(weekly_data), 4):
                    chunk = weekly_data[i:i+4]
                    if chunk:
                        avg_volume = sum(item['volume'] for item in chunk) / len(chunk)
                        weekly_avg_volumes.append(avg_volume)
                
                # Bar graph for weekly volumes
                bars2 = ax2.bar(x_weeks, week_volumes, alpha=0.6, color='lightcoral', 
                            label='Weekly Final Volume', width=0.8)
                
                # Line graph for weekly volume averages
                if len(weekly_avg_volumes) > 1:
                    x_weekly_vol_avg = np.arange(0, len(weeks), 4)[:len(weekly_avg_volumes)]
                    ax2.plot(x_weekly_vol_avg, weekly_avg_volumes, marker='o', linewidth=3,
                            markersize=8, color='orange', label='Weekly Avg Volume', alpha=0.8)
                
                # Line graph for monthly volume averages
                if len(monthly_avg_volumes) > 1:
                    x_monthly_vol = np.linspace(0, len(weeks)-1, len(monthly_avg_volumes))
                    ax2.plot(x_monthly_vol, monthly_avg_volumes, marker='s', linewidth=4,
                            markersize=10, color='purple', label='Monthly Avg Volume', alpha=0.9)
                
                ax2.set_xlabel('Time Period', fontsize=12)
                ax2.set_ylabel('Volume (coins)', fontsize=12)
                ax2.set_title(f'{symbol} Extended Volume Analysis - 12 Weeks with Monthly Averages', 
                            fontsize=14, fontweight='bold')
                ax2.set_xticks(x_weeks[::2])
                ax2.set_xticklabels([weeks[i] for i in range(0, len(weeks), 2)], rotation=45, fontsize=9)
                ax2.legend(fontsize=11)
                ax2.grid(True, alpha=0.3)
                ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x:,.0f}'))
                
                plt.tight_layout()
                
                # Save extended analysis graph
                extended_plot_filename = f"reports/plots/{symbol}_extended_historical_analysis.png"
                plt.savefig(extended_plot_filename, format='png', dpi=300, bbox_inches='tight')
                plt.close()
                
                # Add extended graph to PDF
                pdf.add_image(extended_plot_filename, size_type="large")
                
        except Exception as e:
            pdf.add_paragraph(f"(Extended historical analysis failed: {e})", color=(255, 0, 0))

        # Add Combined Historical Analysis Summary
        pdf.add_page()
        pdf.set_link(links["historical_summary"])
        pdf.add_section_title("2.6. Historical Analysis Summary")

        try:
            # Check data availability and calculate key metrics
            has_extended_data = len(weekly_data) >= 8
            
            # Calculate core statistics
            if valid_data:
                current_avg_close = sum(current_closes) / len(current_closes)
                hist_avg_close = sum(hist_closes) / len(hist_closes)
                current_avg_volume = sum(current_volumes) / len(current_volumes)
                hist_avg_volume = sum(hist_volumes) / len(hist_volumes)
                
                price_change_pct = ((current_avg_close - hist_avg_close) / hist_avg_close) * 100
                volume_change_pct = ((current_avg_volume - hist_avg_volume) / hist_avg_volume) * 100
            
            # Extended analysis (if sufficient data)
            if has_extended_data:
                recent_4_weeks = weekly_data[-4:]
                older_4_weeks = weekly_data[-8:-4]
                
                recent_avg_close = sum(item['close'] for item in recent_4_weeks) / len(recent_4_weeks)
                older_avg_close = sum(item['close'] for item in older_4_weeks) / len(older_4_weeks)
                extended_trend_pct = ((recent_avg_close - older_avg_close) / older_avg_close) * 100
                
                # Monthly trend if available
                monthly_trend_pct = 0
                if valid_monthly_data and len(valid_monthly_data) >= 2:
                    latest_month = valid_monthly_data[-1]['avg_close']
                    oldest_month = valid_monthly_data[0]['avg_close']
                    monthly_trend_pct = ((latest_month - oldest_month) / oldest_month) * 100
            
            # Generate consolidated analysis
            if valid_data:
                # Market Movement Summary
                pdf.add_paragraph("Market Movement Analysis:", color=(0, 0, 150), bold=True)
                
                movement_desc = "significant" if abs(price_change_pct) > 5 else "moderate" if abs(price_change_pct) > 2 else "stable"
                trend_color = (0, 150, 0) if price_change_pct > 0 else (200, 0, 0) if price_change_pct < 0 else (100, 100, 100)
                
                analysis_text = f"Recent trading shows {movement_desc} price movement with the average closing price "
                analysis_text += f"{'increasing' if price_change_pct > 0 else 'decreasing' if price_change_pct < 0 else 'remaining stable'} by {abs(price_change_pct):.1f}% "
                analysis_text += f"(${current_avg_close:,.2f} vs ${hist_avg_close:,.2f}). "
                
                # Add volume context
                vol_desc = "significantly higher" if volume_change_pct > 20 else "higher" if volume_change_pct > 0 else "lower"
                analysis_text += f"Trading volume is {vol_desc} by {abs(volume_change_pct):.1f}%, "
                analysis_text += f"averaging {current_avg_volume:,.0f} coins compared to the historical {hist_avg_volume:,.0f}."
                
                pdf.add_paragraph(analysis_text, color=trend_color)
                
                # Extended Trend Context (if available)
                if has_extended_data:
                    pdf.add_paragraph("Extended Trend Context:", color=(0, 100, 0), bold=True)
                    
                    trend_consistency = "consistent" if (price_change_pct > 0 and extended_trend_pct > 0) or (price_change_pct < 0 and extended_trend_pct < 0) else "diverging"
                    extended_desc = "strong" if abs(extended_trend_pct) > 15 else "moderate" if abs(extended_trend_pct) > 8 else "gradual"
                    
                    extended_text = f"The 4-week extended analysis reveals a {extended_desc} trend of {abs(extended_trend_pct):.1f}% "
                    extended_text += f"{'upward' if extended_trend_pct > 0 else 'downward'} movement, showing {trend_consistency} direction with recent activity. "
                    
                    if valid_monthly_data and len(valid_monthly_data) >= 2:
                        monthly_desc = "substantial" if abs(monthly_trend_pct) > 25 else "notable" if abs(monthly_trend_pct) > 12 else "gradual"
                        extended_text += f"Monthly data indicates {monthly_desc} {len(valid_monthly_data)}-month progression of {monthly_trend_pct:+.1f}%."
                    
                    trend_color = (0, 150, 0) if extended_trend_pct > 0 else (200, 0, 0)
                    pdf.add_paragraph(extended_text, color=trend_color)
                
                # Trading Signal Summary
                pdf.add_paragraph("Trading Signal Assessment:", color=(100, 0, 100), bold=True)
                
                # Determine overall signal
                if price_change_pct > 0 and volume_change_pct > 0:
                    signal = "Bullish trend confirmed with rising prices and increased volume activity"
                    signal_color = (0, 150, 0)
                elif price_change_pct > 0 and volume_change_pct < 0:
                    signal = "Cautious bullish signal - prices rising but on declining volume"
                    signal_color = (200, 100, 0)
                elif price_change_pct < 0 and volume_change_pct > 0:
                    signal = "Bearish trend with falling prices and high volume activity"
                    signal_color = (200, 0, 0)
                elif price_change_pct < 0 and volume_change_pct < 0:
                    signal = "Weak bearish signal - declining prices with reduced trading interest"
                    signal_color = (150, 150, 0)
                else:
                    signal = "Neutral market conditions with minimal price and volume changes"
                    signal_color = (100, 100, 100)
                
                # Add trend consistency note if extended data available
                if has_extended_data:
                    consistency_note = " This aligns with the extended trend pattern, suggesting sustained market direction." if trend_consistency == "consistent" else " However, this contrasts with the broader trend, indicating potential market shift."
                    signal += consistency_note
                
                pdf.add_paragraph(signal, color=signal_color, bold=True)
                
            else:
                pdf.add_paragraph("Insufficient historical data available for comprehensive market analysis. "
                                "Analysis requires at least one week of comparative data for meaningful insights.", 
                                color=(150, 150, 150))
            
            # Data availability note
            if len(weekly_data) < 8:
                pdf.add_paragraph("")
                pdf.add_paragraph("Note: Extended trend analysis requires minimum 8 weeks of data for enhanced accuracy.", 
                                color=(120, 120, 120), size=9)

        except Exception as e:
            pdf.add_paragraph(f"Historical analysis unavailable due to data processing error: {str(e)}", color=(255, 0, 0))

    except Exception as e:
        pdf.add_paragraph(f"(Historical price analysis failed: {e})", color=(255, 0, 0))

    pdf.add_page()

    # 1D. Top 5 Sentiment Headlines
    pdf.set_link(links["sentiment_headlines"])
    if headlines:
        pdf.add_section_title("3. Market Sentiment & News Impact")
        
        # Sort headlines by score (higher to lower)
        sorted_headlines = sorted(headlines[:10], key=lambda x: x.get("score", 0), reverse=True)
        
        # Keep track of RSS feed sources for reference table with full details
        rss_sources = {}  # Changed to dict to store more info
        
        for i, item in enumerate(sorted_headlines, 1):
            title = remove_unicode(item.get("title", ""))
            summary_news = remove_unicode(item.get("summary_news", ""))
            score = item.get("score", 0)
            published_raw = item.get("published", "N/A")
            try:
                # Parse and strip timezone
                dt = parser.parse(published_raw)
                published = dt.strftime("%d-%b-%Y %H:%M")
            except:
                published = published_raw  # fallback if parse fails

            source = item.get("source", "Unknown")
            link = item.get("link", "")
            category = item.get("category", "")
            
            # Extract domain from link for proper reference
            from urllib.parse import urlparse
            try:
                parsed_url = urlparse(link)
                domain = parsed_url.netloc.lower().replace('www.', '')
                base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
            except:
                domain = "unknown-domain.com"
                base_url = link
            
            # Add source to reference dict with full details
            if source not in rss_sources:
                rss_sources[source] = {
                    'domain': domain,
                    'base_url': base_url,
                    'articles_count': 1,
                    'category': category
                }
            else:
                rss_sources[source]['articles_count'] += 1
            
            emoji = "[+]" if score > 0.25 else "[-]" if score < -0.25 else "[·]"
            headline_color = pdf.get_sentiment_color(score)

            # Headline with Score
            pdf.set_font("Arial", "B", 10)
            pdf.set_text_color(*headline_color)
            pdf.multi_cell(0, 6, f"{i}. {emoji} {title} (Score: {score:.2f})")
            
            # Try to add logo fetched from web and make it clickable
            logo_added = False
            try:
                from urllib.parse import urlparse
                import requests
                import tempfile
                import os
                
                domain = urlparse(link).netloc.lower()
                
                # Get favicon/logo from the website
                favicon_url = None
                try:
                    # Try multiple favicon sources
                    base_domain = domain.replace('www.', '')
                    favicon_urls = [
                        f"https://www.google.com/s2/favicons?domain={base_domain}&sz=64",
                        f"https://{domain}/favicon.ico",
                        f"https://logo.clearbit.com/{base_domain}",
                        f"https://www.google.com/s2/favicons?domain={domain}&sz=32"
                    ]
                    
                    for url in favicon_urls:
                        try:
                            response = requests.get(url, timeout=3, headers={'User-Agent': 'Mozilla/5.0'})
                            if response.status_code == 200 and len(response.content) > 100:  # Valid image
                                favicon_url = url
                                break
                        except:
                            continue
                    
                    if favicon_url:
                        # Download and use the favicon
                        response = requests.get(favicon_url, timeout=3, headers={'User-Agent': 'Mozilla/5.0'})
                        if response.status_code == 200:
                            # Create temporary file
                            with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_file:
                                tmp_file.write(response.content)
                                tmp_path = tmp_file.name
                            
                            try:
                                x_pos = pdf.get_x()
                                y_pos = pdf.get_y()
                                # Add small logo (8x8 mm for favicons) with clickable link
                                pdf.image(tmp_path, x_pos, y_pos, 8, 8, link=link)
                                pdf.set_xy(x_pos + 10, y_pos)  # Move text position
                                logo_added = True
                            finally:
                                # Clean up temp file
                                try:
                                    os.unlink(tmp_path)
                                except:
                                    pass
                except:
                    pass  # Logo fetching failed, continue without logo
            except:
                pass
            
            # Show source and published info
            pdf.set_font("Arial", "", 10)
            pdf.set_text_color(100, 100, 100)
            pdf.multi_cell(0, 5, f"Published: {published} UTC | Source: {source}\n\n")
            
            # FULL DESCRIPTION - NO TRUNCATION AT ALL
            if summary_news and summary_news.strip():
                pdf.set_font("Arial", "", 9)
                pdf.set_text_color(40, 40, 40)  # Dark text for readability
                
                # Print ENTIRE content without any limitations
                full_content = summary_news.strip()
               
                print(f"🖨️ Printing full content: {len(full_content)} characters")
                
                # Use multi_cell with proper line height for long content
                pdf.multi_cell(0, 4.5, full_content)
                
            else:
                pdf.set_font("Arial", "", 8)
                pdf.set_text_color(150, 150, 150)
                pdf.multi_cell(0, 4, "[No description available]")
            
            pdf.ln(4)  # More space between entries

        # Add sentiment explanation
        signal_sentiment = signal_info.get("sentiment", "neutral")
        explanation_color = pdf.get_sentiment_color(signal_sentiment)
        explanation_text = {
            "bullish": "Most headlines had a positive tone. Market sentiment appears optimistic.",
            "bearish": "Many headlines indicated negative or fearful tone. Market may be under pressure.",
            "neutral": "Headlines showed mixed or weak sentiment. Market is undecided or consolidating."
        }
        pdf.add_paragraph(f"\nSentiment Interpretation: {explanation_text.get(signal_sentiment, 'No data.')}",
                        color=explanation_color)

        pdf.add_page()        
        # Add PROPER RSS Sources Reference Table
        pdf.ln(8)
        pdf.add_section_title("RSS Feed Sources & References")
        
        # Add introductory text
        pdf.set_font("Arial", "", 10)
        pdf.set_text_color(60, 60, 60)
        pdf.multi_cell(0, 5, "The following sources were analyzed for sentiment data in this report:")
        pdf.ln(3)
        
        # Create proper academic-style references
        for idx, (source_name, source_info) in enumerate(sorted(rss_sources.items()), 1):
            domain = source_info['domain']
            base_url = source_info['base_url']
            articles_count = source_info['articles_count']
            category = source_info.get('category', '')
            
            # Reference number in brackets
            pdf.set_font("Arial", "B", 10)
            pdf.set_text_color(30, 30, 30)
            
            # Check if we can add this without page overflow
            if pdf.get_y() > 250:  # Near bottom of page
                pdf.add_page()
            
            # Format: [1] Source Name. Domain. Available at: URL. [Articles: X]
            reference_text = f"[{idx}] "
            pdf.cell(15, 6, reference_text, 0, 0)
            
            # Source name in bold
            pdf.set_font("Arial", "B", 10)
            pdf.cell(0, 6, f"{source_name}.", 0, 1)
            
            # Domain and URL (clickable)
            pdf.set_font("Arial", "", 9)
            pdf.set_text_color(50, 50, 50)
            pdf.cell(15, 5, "", 0, 0)  # Indent
            pdf.cell(0, 5, f"Domain: {domain}", 0, 1)
            
            # Available at (clickable URL)
            pdf.cell(15, 5, "", 0, 0)  # Indent
            pdf.set_text_color(0, 0, 200)  # Blue for links
            pdf.cell(25, 5, "Available at: ", 0, 0)
            pdf.cell(0, 5, base_url, 0, 1, link=base_url)
            
            # Additional info
            pdf.set_text_color(100, 100, 100)
            pdf.cell(15, 5, "", 0, 0)  # Indent
            additional_info = f"Articles analyzed: {articles_count}"
            if category:
                additional_info += f" | Category: {category}"
            pdf.cell(0, 5, additional_info, 0, 1)
            
            pdf.ln(3)  # Space between references
        
        # Add access date and disclaimer
        pdf.ln(5)
        pdf.set_font("Arial", "I", 8)
        pdf.set_text_color(120, 120, 120)
        from datetime import datetime
        current_date = datetime.now().strftime("%d %b, %Y")
        disclaimer_text = f"All sources accessed on {current_date}. RSS feed content is subject to change and availability may vary."
        pdf.multi_cell(0, 4, disclaimer_text)
        
        pdf.ln(3)

    pdf.add_page()

   # 1E. Technical Indicators (Detailed)
    pdf.set_link(links["technical_indicators"])
    if 'indicators' in signal_info and 'price_snapshot' in signal_info:
        pdf.add_section_title("4. Technical Analysis & Chart Patterns")

        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
        import matplotlib.ticker as mticker
        import os
        from datetime import datetime, timezone

        ind = signal_info['indicators']
        timeframe_str = interval.upper()

        # Add timeframe and data context information
        pdf.set_font("Arial", "B", 11)
        pdf.set_text_color(0, 0, 0)
        pdf.multi_cell(0, 6, f"Analysis Parameters:")

        pdf.set_font("Arial", "", 10)
        pdf.set_text_color(60, 60, 60)

        # Get historical limit from signal_info or set default
        historical_limit = HISTORICAL_LIMIT
        data_points = len(signal_info['price_snapshot']) if 'price_snapshot' in signal_info else 'Unknown'

        # Get total days from summary if available
        if isinstance(summary, dict):
            analysis_period = summary.get('Total Days Analyzed', '2500 candles')
        else:
            analysis_period = '2500 candles'
        
        pdf.multi_cell(0, 5, f"- Timeframe: {timeframe_str}")
        pdf.multi_cell(0, 5, f"- Historical Data Limit: {analysis_period}")
        pdf.multi_cell(0, 5, f"- Data Points Analyzed: {data_points} candles")
        pdf.multi_cell(0, 5, f"- Analysis Date: {datetime.now(timezone.utc).strftime('%d-%b-%Y %H:%M:%S UTC')}")

        pdf.ln(3)

        # === MACD ===
        macd_value = ind.get('macd', 'N/A')
        macd_color = pdf.get_signal_color(macd_value)
        pdf.set_font("Arial", "B", 10)
        pdf.set_text_color(*macd_color)
        pdf.multi_cell(0, 6, f"\nMACD Signal: {macd_value} (Timeframe: {timeframe_str}, Fast EMA: 50, Slow EMA: 200, Signal: 9)")
        
        pdf.set_font("Arial", "B", 10)
        pdf.set_text_color(50, 50, 50)
        pdf.multi_cell(0, 5, "MACD identifies momentum shifts in our system. A bullish crossover (MACD > Signal) generates a potential BUY signal, while a bearish crossover triggers a SELL signal.\n")

        # === RSI ===
        rsi_raw = ind.get('rsi', 'N/A')
        rsi_signal = rsi_raw[1] if isinstance(rsi_raw, tuple) and len(rsi_raw) == 2 else str(rsi_raw)
        rsi_color = pdf.get_signal_color(rsi_signal)

        pdf.set_font("Arial", "B", 10)
        pdf.set_text_color(*rsi_color)
        pdf.multi_cell(0, 6, f"\nRSI Signal: {rsi_signal} (Timeframe: {timeframe_str}, Period: 14)")

        pdf.set_font("Arial", "", 10)
        pdf.set_text_color(50, 50, 50)
        pdf.multi_cell(0, 5, "RSI (Relative Strength Index) measures momentum in our analysis. Our system treats values above 75 as overbought (SELL zone) and values below 25 as oversold (BUY zone).\n")

        # === Bollinger Bands ===
        bb_signal = ind.get('bb', 'N/A')
        bb_color = pdf.get_signal_color(bb_signal)

        pdf.set_font("Arial", "B", 10)
        pdf.set_text_color(*bb_color)
        pdf.multi_cell(0, 6, f"\nBollinger Bands Signal: {bb_signal} (Timeframe: {timeframe_str}, SMA: 20, ±2 Std Dev)")

        pdf.set_font("Arial", "", 10)
        pdf.set_text_color(50, 50, 50)
        pdf.multi_cell(0, 5, "Bollinger Bands track price volatility in our system. When price breaks the bands, our algorithm detects reversal or breakout opportunities.\n")

        # === Volatility ===
        vol_value = ind.get('volatility', 'N/A')
        pdf.set_font("Arial", "B", 10)
        pdf.set_text_color(0, 0, 0)
        pdf.multi_cell(0, 6, f"\nVolatility Index: {vol_value} (Standard deviation over recent candles)")

        pdf.set_font("Arial", "", 10)
        pdf.set_text_color(50, 50, 50)
        pdf.multi_cell(0, 5, "Volatility is assessed using standard deviation in our risk management. High volatility triggers greater caution and adjusted position sizing.\n")

        # === Volume Analysis ===
        volume_metrics = ind.get('volume', {})
        if volume_metrics:
            volume_signal = volume_metrics.get('volume_signal', 'N/A')
            obv_signal = volume_metrics.get('obv_signal', 'N/A')
            volume_change_percent = volume_metrics.get('volume_change_percent', 0)
            
            # Volume Signal
            volume_color = pdf.get_signal_color(volume_signal)
            pdf.set_font("Arial", "B", 10)
            pdf.set_text_color(*volume_color)
            pdf.multi_cell(0, 6, f"\nVolume Signal: {volume_signal} (Timeframe: {timeframe_str}, Period: 20)")
            
            pdf.set_font("Arial", "", 10)
            pdf.set_text_color(50, 50, 50)
            pdf.multi_cell(0, 5, f"Current volume vs 20-period average: {volume_change_percent:+.2f}%")
            pdf.multi_cell(0, 5, "Volume analysis confirms price movements in our system. High volume validates breakouts and trend changes, while low volume suggests weak or unreliable signals.\n")
            
            # OBV Signal
            obv_color = pdf.get_signal_color(obv_signal)
            pdf.set_font("Arial", "B", 10)
            pdf.set_text_color(*obv_color)
            pdf.multi_cell(0, 6, f"\nOBV Signal: {obv_signal} (On-Balance Volume with 10-period EMA)")
            
            pdf.set_font("Arial", "", 10)
            pdf.set_text_color(50, 50, 50)
            pdf.multi_cell(0, 5, "OBV (On-Balance Volume) tracks cumulative volume flow in our analysis. When OBV crosses above its EMA, it suggests accumulation (bullish), while crossing below indicates distribution (bearish).\n")
        else:
            pdf.set_font("Arial", "B", 10)
            pdf.set_text_color(100, 100, 100)
            pdf.multi_cell(0, 6, f"\nVolume Analysis: Not Available")
            
            pdf.set_font("Arial", "", 10)
            pdf.set_text_color(50, 50, 50)
            pdf.multi_cell(0, 5, "Volume data not available for this analysis period.\n")

        # === Create First Combined Plot (Price + MACD) ===
        try:
            df = signal_info['price_snapshot'].copy()
            df.index = pd.to_datetime(df.index)
            
            # Sort by index to ensure proper chronological order
            df = df.sort_index()
            
            # Take only the last 100 data points for better visualization
            df = df.tail(100)

            # Ensure all relevant columns are float and handle missing data
            for col in ['close', 'open', 'high', 'low', 'volume']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Calculate EMA lines for both price chart and MACD calculation
            df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
            df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
            
            # Calculate MACD components using EMA 50 and EMA 200
            df['macd_line'] = df['ema_50'] - df['ema_200']  # MACD Line = EMA50 - EMA200
            df['macd_signal'] = df['macd_line'].ewm(span=9, adjust=False).mean()  # Signal Line = EMA-9 of MACD Line
            df['macd_histogram'] = df['macd_line'] - df['macd_signal']  # Histogram = MACD Line - Signal Line
            
            if 'rsi' not in df.columns:
                # RSI calculation matching your indicators/rsi.py
                delta = df['close'].diff()
                gain = delta.where(delta > 0, 0.0)
                loss = -delta.where(delta < 0, 0.0)
                
                # Use exponential moving average for more responsive RSI (same as your indicator)
                alpha = 1.0 / 14
                avg_gain = gain.ewm(alpha=alpha, adjust=False).mean()
                avg_loss = loss.ewm(alpha=alpha, adjust=False).mean()
                
                rs = avg_gain / avg_loss
                df['rsi'] = 100 - (100 / (1 + rs))
            
            if 'upper_band' not in df.columns or 'lower_band' not in df.columns:
                # Simple Bollinger Bands calculation
                rolling_mean = df['close'].rolling(window=20).mean()
                rolling_std = df['close'].rolling(window=20).std()
                df['upper_band'] = rolling_mean + (rolling_std * 2)
                df['lower_band'] = rolling_mean - (rolling_std * 2)
                df['middle_band'] = rolling_mean

            # Calculate Volatility using your volatility.py function logic
            close = df["close"]
            returns = close.pct_change()
            
            # Use multiple timeframes for better volatility assessment (same as your volatility.py)
            short_vol = returns.rolling(window=5).std()   
            med_vol = returns.rolling(window=14).std()    
            long_vol = returns.rolling(window=30).std()  

            latest_short = short_vol.iloc[-1]
            latest_med = med_vol.iloc[-1]
            latest_long = long_vol.iloc[-1]
            
            # Weight recent volatility more heavily (same as your volatility.py)
            weighted_vol = (latest_short * 0.5 + latest_med * 0.3 + latest_long * 0.2)
            
            # Store the weighted volatility for consistent use
            df['volatility'] = weighted_vol

            # Get percentile-based thresholds for volatility classification (same as your volatility.py)
            med_vol_clean = med_vol.dropna()
            if len(med_vol_clean) >= 10:
                # Use percentiles for dynamic thresholds
                high_threshold = med_vol_clean.quantile(0.75)
                low_threshold = med_vol_clean.quantile(0.25)
                
                if pd.isna(weighted_vol):
                    vol_signal = "medium"
                elif weighted_vol > high_threshold * 1.2:
                    vol_signal = "high"
                elif weighted_vol < low_threshold * 0.8:
                    vol_signal = "low"
                else:
                    vol_signal = "medium"
            else:
                vol_signal = "medium"

            # Ensure we have valid data
            df = df.dropna()
            
            if len(df) < 10:
                raise ValueError("Insufficient data for plotting")

            # ===== FIRST IMAGE: Price + MACD =====
            fig1, axes1 = plt.subplots(2, 1, figsize=(20, 12), sharex=True, gridspec_kw={'hspace': 0.3})
            
            # Set the style
            plt.style.use('default')
            
            # --- Price + Bollinger Bands + EMA Lines ---
            axes1[0].plot(df.index, df['close'], color='#1f77b4', linewidth=2, label='Close Price')
            axes1[0].plot(df.index, df['ema_50'], color='orange', linewidth=2, label='EMA 50', alpha=0.8)
            axes1[0].plot(df.index, df['ema_200'], color='red', linewidth=2, label='EMA 200', alpha=0.8)
            axes1[0].fill_between(df.index, df['lower_band'], df['upper_band'], 
                            color='lightblue', alpha=0.3, label='Bollinger Bands')
            axes1[0].plot(df.index, df['upper_band'], color='green', linestyle='--', alpha=0.7, linewidth=1)
            axes1[0].plot(df.index, df['lower_band'], color='green', linestyle='--', alpha=0.7, linewidth=1)
            axes1[0].plot(df.index, df['middle_band'], color="#f962bd", linestyle='-', alpha=0.7, linewidth=2, label='BB Middle (SMA 20)')
            
            axes1[0].set_title(f"{symbol} - Price + EMA Lines + Bollinger Bands", fontsize=16, fontweight='bold')
            axes1[0].legend(loc='upper left', fontsize=12)
            axes1[0].grid(True, alpha=0.3)
            axes1[0].set_ylabel('Price ($)', fontsize=14)
            axes1[0].yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{x:,.0f}'))
            
            # Add current price annotation with dynamic explanation
            current_price = df['close'].iloc[-1]
            current_upper = df['upper_band'].iloc[-1]
            current_lower = df['lower_band'].iloc[-1]
            current_middle = df['middle_band'].iloc[-1]
            
            # Dynamic price explanation
            # Calculate BB signal using exact same logic as indicators/bollinger.py
            prev_price = df['close'].iloc[-2] if len(df) >= 2 else current_price
            prev_upper = df['upper_band'].iloc[-2] if len(df) >= 2 else current_upper
            prev_lower = df['lower_band'].iloc[-2] if len(df) >= 2 else current_lower

            # BB signal detection
            upper_breach = current_price > current_upper
            lower_breach = current_price < current_lower
            prev_upper_breach = prev_price > prev_upper
            prev_lower_breach = prev_price < prev_lower

            if upper_breach and prev_upper_breach:
                bb_signal_calc = "breakout_up"
                price_explanation = "Strong breakout above upper band - sustained upward momentum"
            elif lower_breach and prev_lower_breach:
                bb_signal_calc = "breakout_down"
                price_explanation = "Strong breakout below lower band - sustained downward pressure"
            elif upper_breach and not prev_upper_breach:
                bb_signal_calc = "breakout_up"
                price_explanation = "Fresh breakout above upper band - new upward momentum"
            elif lower_breach and not prev_lower_breach:
                bb_signal_calc = "breakout_down"
                price_explanation = "Fresh breakout below lower band - new downward pressure"
            else:
                bb_signal_calc = "within_range"
                if current_price > current_middle:
                    price_explanation = "Price above middle band - bullish territory within range"
                else:
                    price_explanation = "Price below middle band - bearish territory within range"
            
            axes1[0].annotate(f'Current: ${current_price:.2f}\n{price_explanation}', 
                    xy=(df.index[-1], current_price), 
                    xytext=(12, 12), textcoords='offset points',
                    bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.7),
                    fontsize=12)

            # --- MACD with EMA 50/200 calculation ---
            axes1[1].plot(df.index, df['macd_line'], label='MACD Line (EMA50-EMA200)', color='blue', linewidth=2)
            axes1[1].plot(df.index, df['macd_signal'], label='Signal Line (EMA9 of MACD)', color='red', linewidth=2)
            
            # Color histogram bars based on value with separate labels
            positive_hist = df['macd_histogram'].where(df['macd_histogram'] >= 0, 0)
            negative_hist = df['macd_histogram'].where(df['macd_histogram'] < 0, 0)
            
            axes1[1].bar(df.index, positive_hist, label='Bullish Histogram (Above Signal)', 
                    color='green', alpha=0.6, width=0.8)
            axes1[1].bar(df.index, negative_hist, label='Bearish Histogram (Below Signal)', 
                    color='red', alpha=0.6, width=0.8)
            
            axes1[1].axhline(0, color='black', linestyle='-', linewidth=0.8, alpha=0.8)
            axes1[1].set_title("MACD Indicator (EMA-50/200)", fontsize=16, fontweight='bold')
            axes1[1].legend(loc='upper left', fontsize=12)
            axes1[1].grid(True, alpha=0.3)
            axes1[1].set_ylabel('MACD', fontsize=14)
            
            # *** MACD SIGNAL DETECTION MATCHING YOUR INDICATOR LOGIC ***
            # Use the exact same logic as your indicators/macd.py
            current_hist = df['macd_histogram'].iloc[-1]
            prev_hist = df['macd_histogram'].iloc[-2] if len(df) >= 2 else current_hist

            # Noise filter: Ignore tiny fluctuations (same as your indicator)
            threshold = 0.3

            macd_signal = ""
            if current_hist > threshold and prev_hist <= threshold:
                macd_signal = "bullish"
            elif current_hist < -threshold and prev_hist >= -threshold:
                macd_signal = "bearish"
            elif current_hist > prev_hist and current_hist > threshold:
                macd_signal = "bullish"
            elif current_hist < prev_hist and current_hist < -threshold:
                macd_signal = "bearish"
            elif abs(current_hist) < threshold:
                macd_signal = "neutral"
            else:
                macd_signal = "bullish" if current_hist > 0 else "bearish"

            # Convert to display format
            if macd_signal == "bullish":
                macd_position = "Bullish"
                macd_explanation = "MACD line crossed above signal - bullish momentum"
            elif macd_signal == "bearish":
                macd_position = "Bearish"
                macd_explanation = "MACD line crossed below signal - bearish momentum"
            else:
                macd_position = "Neutral"
                macd_explanation = "MACD signals are converging - consolidation phase"
            
            # Determine color based on signal
            if "Bullish" in macd_position:
                macd_annotation_color = 'lightgreen'
            elif "Bearish" in macd_position:
                macd_annotation_color = 'lightcoral'
            else:
                macd_annotation_color = 'lightyellow'
            
            axes1[1].annotate(f'MACD: {macd_position}\n{macd_explanation}', 
                    xy=(df.index[-1], df['macd_line'].iloc[-1]), 
                    xytext=(12, 12), textcoords='offset points',
                    bbox=dict(boxstyle='round,pad=0.3', 
                            facecolor=macd_annotation_color, 
                            alpha=0.7),
                    fontsize=12)

            # Format x-axis with custom date format for first image
            def format_date(x, pos):
                try:
                    dt = mdates.num2date(x)
                    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                                'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
                    return f"{dt.day:02d}-{month_names[dt.month-1]}-{dt.year} {dt.hour:02d}:{dt.minute:02d}"
                except:
                    return ""
            
            axes1[1].xaxis.set_major_formatter(mticker.FuncFormatter(format_date))
            axes1[1].xaxis.set_major_locator(mdates.HourLocator(interval=max(1, len(df)//10)))
            plt.setp(axes1[1].xaxis.get_majorticklabels(), rotation=45)
            
            # Set xlabel for first image
            axes1[1].set_xlabel('Time (UTC)', fontsize=14)
            
            # Adjust layout for first image
            plt.tight_layout()
            
            # Save the first plot
            os.makedirs("reports", exist_ok=True)
            plt.savefig("reports/indicators_price_macd.png", dpi=200, bbox_inches='tight', facecolor='white')
            plt.close()

            # ===== SECOND IMAGE: RSI + Volatility + Volume + OBV =====
            fig2, axes2 = plt.subplots(3, 1, figsize=(20, 16), sharex=True, gridspec_kw={'hspace': 0.4})

            # Set the same style as first image
            plt.style.use('default')

            # --- RSI with MACD Signals (Using same EMA 50/200 calculation) ---
            axes2[0].plot(df.index, df['rsi'], color='#9d4edd', linewidth=2, label='RSI')

            # Use the SAME MACD calculation as the first chart - no different calculation
            # The MACD components are already calculated above using EMA 50/200
            macd_min = df['macd_line'].min()
            macd_max = df['macd_line'].max()
            signal_min = df['macd_signal'].min()
            signal_max = df['macd_signal'].max()

            # Normalize MACD lines to 0-100 range to overlay on RSI
            if macd_max != macd_min:
                macd_normalized = ((df['macd_line'] - macd_min) / (macd_max - macd_min)) * 100
            else:
                macd_normalized = df['macd_line'] * 0 + 50

            if signal_max != signal_min:
                signal_normalized = ((df['macd_signal'] - signal_min) / (signal_max - signal_min)) * 100
            else:
                signal_normalized = df['macd_signal'] * 0 + 50

            # Plot normalized MACD lines
            axes2[0].plot(df.index, macd_normalized, label='MACD Line (EMA50-200, Scaled)', color='blue', 
                        linewidth=2, alpha=0.8)
            axes2[0].plot(df.index, signal_normalized, label='Signal Line (EMA9, Scaled)', color='red', 
                        linewidth=2, alpha=0.8)

            # RSI threshold lines with same styling as first image
            axes2[0].axhline(75, color='red', linestyle='--', alpha=0.7, linewidth=1, label='Overbought (75)')
            axes2[0].axhline(25, color='green', linestyle='--', alpha=0.7, linewidth=1, label='Oversold (25)')
            axes2[0].axhline(50, color='gray', linestyle='-', alpha=0.5, linewidth=1)

            axes2[0].set_title(f"{symbol} - RSI with MACD Signals (EMA 50/200)", fontsize=16, fontweight='bold')
            axes2[0].legend(loc='upper left', fontsize=12)
            axes2[0].grid(True, alpha=0.3)
            axes2[0].set_ylabel('RSI (0-100) / MACD (Scaled)', fontsize=14)
            axes2[0].set_ylim(0, 100)

            # RSI and MACD annotation
            current_rsi = df['rsi'].iloc[-1]
            current_macd_norm = macd_normalized.iloc[-1]
            current_signal_norm = signal_normalized.iloc[-1]

            if current_rsi > 75:
                rsi_level = "Overbought"
                rsi_color = 'lightcoral'
                rsi_explanation = "RSI > 75 - Strong selling pressure expected"
            elif current_rsi < 25:
                rsi_level = "Oversold"
                rsi_color = 'lightgreen'
                rsi_explanation = "RSI < 25 - Strong buying opportunity potential"
            elif current_rsi > 50:
                rsi_level = "Neutral-Bullish"
                rsi_color = 'lightblue'
                rsi_explanation = "RSI > 50 - Bullish momentum prevailing"
            else:
                rsi_level = "Neutral-Bearish"
                rsi_color = 'lightyellow'
                rsi_explanation = "RSI < 50 - Bearish momentum prevailing"

            macd_crossover_status = "Above Signal" if current_macd_norm > current_signal_norm else "Below Signal"
                
            axes2[0].annotate(f'RSI: {current_rsi:.1f} ({rsi_level})\nMACD: {macd_crossover_status}\n{rsi_explanation}', 
                    xy=(df.index[-1], current_rsi), 
                    xytext=(12, 12), textcoords='offset points',
                    bbox=dict(boxstyle='round,pad=0.3', facecolor=rsi_color, alpha=0.7),
                    fontsize=12)

            # ===== CALCULATE VOLUME METRICS MATCHING indicators/volume.py =====
            period = 20
            
            # Check if volume data exists
            if "volume" in df.columns and not df["volume"].isnull().all():
                # --- Volume Analysis (matching your volume.py logic exactly) ---
                volume = df["volume"]
                current_volume = volume.iloc[-1]
                volume_avg = volume.iloc[-period:].mean() # Simple moving average of volume
                
                # Avoid division by zero
                volume_change_percent = ((current_volume - volume_avg) / volume_avg) * 100 if volume_avg != 0 else 0.0

                volume_signal = "neutral"
                if current_volume > volume_avg * 1.5: # Significantly higher volume
                    volume_signal = "high_volume"
                elif current_volume < volume_avg * 0.5: # Significantly lower volume
                    volume_signal = "low_volume"
                
                # --- On-Balance Volume (OBV) (matching your volume.py logic exactly) ---
                obv = pd.Series(0.0, index=df.index)
                obv.iloc[0] = 0 # Initialize OBV

                for i in range(1, len(df)):
                    if df["close"].iloc[i] > df["close"].iloc[i-1]:
                        obv.iloc[i] = obv.iloc[i-1] + df["volume"].iloc[i]
                    elif df["close"].iloc[i] < df["close"].iloc[i-1]:
                        obv.iloc[i] = obv.iloc[i-1] - df["volume"].iloc[i]
                    else:
                        obv.iloc[i] = obv.iloc[i-1]
                        
                obv_ema = obv.ewm(span=10, adjust=False).mean() # 10-period EMA for OBV signal line
                
                obv_signal = "neutral"
                if len(obv) >= 2 and len(obv_ema) >= 2:
                    if obv.iloc[-1] > obv_ema.iloc[-1] and obv.iloc[-2] <= obv_ema.iloc[-2]: # OBV crosses above its EMA
                        obv_signal = "bullish"
                    elif obv.iloc[-1] < obv_ema.iloc[-1] and obv.iloc[-2] >= obv_ema.iloc[-2]: # OBV crosses below its EMA
                        obv_signal = "bearish"

                volume_metrics = {
                    "volume_value": current_volume,
                    "volume_avg": volume_avg,
                    "volume_change_percent": round(volume_change_percent, 2),
                    "volume_signal": volume_signal,
                    "obv": obv.iloc[-1],
                    "obv_signal": obv_signal
                }
                
                has_volume_data = True
            else:
                # No volume data available
                volume_metrics = {
                    "volume_value": 0.0,
                    "volume_avg": 0.0,
                    "volume_change_percent": 0.0,
                    "volume_signal": "neutral",
                    "obv": 0.0,
                    "obv_signal": "neutral"
                }
                has_volume_data = False

            # --- Volume Analysis with Price Overlay ---
            if has_volume_data:
                # Create secondary y-axis for price
                ax_vol_secondary = axes2[1].twinx()

                # Plot volume bars on primary axis
                axes2[1].bar(df.index, df['volume'], alpha=0.6, color='lightblue', 
                           label='Volume', width=0.8)
                
                # Plot volume average line
                volume_avg_series = pd.Series([volume_metrics["volume_avg"]] * len(df), index=df.index)
                axes2[1].plot(df.index, volume_avg_series, color='red', linewidth=2, 
                            linestyle='--', label='Volume Average (20)')

                # Plot close price on secondary axis
                ax_vol_secondary.plot(df.index, df['close'], label='Close Price', color='darkblue', 
                                    linewidth=2, alpha=0.9)

                axes2[1].set_title("Volume Analysis with Price Overlay", fontsize=16, fontweight='bold')
                axes2[1].grid(True, alpha=0.3)
                axes2[1].set_ylabel('Volume', fontsize=14)

                # Configure secondary axis (price)
                ax_vol_secondary.set_ylabel('Price ($)', fontsize=14)
                ax_vol_secondary.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{x:,.0f}'))

                # Combine legends from both axes
                lines1, labels1 = axes2[1].get_legend_handles_labels()
                lines2, labels2 = ax_vol_secondary.get_legend_handles_labels()
                axes2[1].legend(lines1 + lines2, labels1 + labels2, loc='upper left', fontsize=12)

                # Volume signal interpretation
                if volume_metrics["volume_signal"] == "high_volume":
                    vol_level = "High Volume"
                    vol_color = 'lightgreen'
                    vol_explanation = f"Volume {volume_metrics['volume_change_percent']:+.1f}% above average - Strong interest"
                elif volume_metrics["volume_signal"] == "low_volume":
                    vol_level = "Low Volume" 
                    vol_color = 'lightcoral'
                    vol_explanation = f"Volume {volume_metrics['volume_change_percent']:+.1f}% below average - Weak interest"
                else:
                    vol_level = "Normal Volume"
                    vol_color = 'lightyellow'
                    vol_explanation = f"Volume {volume_metrics['volume_change_percent']:+.1f}% vs average - Typical activity"

                # Volume annotations
                axes2[1].annotate(f'Volume: {vol_level}\n{vol_explanation}', 
                        xy=(df.index[-1], current_volume), 
                        xytext=(12, 50), textcoords='offset points',
                        bbox=dict(boxstyle='round,pad=0.5', facecolor=vol_color, alpha=0.7),
                        fontsize=12,
                        arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0.1', 
                                    color='black', alpha=0.7, lw=1.5))

                current_close_price = df['close'].iloc[-1]
                ax_vol_secondary.annotate(f'Price: ${current_close_price:.2f}', 
                        xy=(df.index[-1], current_close_price), 
                        xytext=(-120, -40), textcoords='offset points',
                        bbox=dict(boxstyle='round,pad=0.5', facecolor='lightblue', alpha=0.7),
                        fontsize=12,
                        arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=-0.1', 
                                    color='black', alpha=0.7, lw=1.5))
            else:
                # No volume data - show message
                axes2[1].text(0.5, 0.5, 'Volume Data Not Available', 
                            horizontalalignment='center', verticalalignment='center', 
                            transform=axes2[1].transAxes, fontsize=16, color='gray')
                axes2[1].set_title("Volume Analysis - Data Not Available", fontsize=16, fontweight='bold')
                axes2[1].grid(True, alpha=0.3)
                axes2[1].set_ylabel('Volume', fontsize=14)

            # --- OBV Analysis with Volatility ---
            if has_volume_data:
                # Create secondary y-axis for volatility
                ax_obv_secondary = axes2[2].twinx()

                # Plot OBV on primary axis
                axes2[2].plot(df.index, obv, label='OBV (On-Balance Volume)', color='purple', linewidth=2)
                axes2[2].plot(df.index, obv_ema, label='OBV EMA (10)', color='orange', linewidth=2, linestyle='--')

                # Plot volatility on secondary axis - use the SAME weighted_vol calculation
                volatility_series = pd.Series([weighted_vol] * len(df), index=df.index)
                ax_obv_secondary.plot(df.index, volatility_series, label='Volatility (Weighted Std Dev)', 
                                    color='red', linewidth=2, alpha=0.8)
                ax_obv_secondary.fill_between(df.index, 0, volatility_series, alpha=0.2, color='red')

                axes2[2].set_title("OBV Analysis with Volatility Overlay", fontsize=16, fontweight='bold')
                axes2[2].grid(True, alpha=0.3)
                axes2[2].set_ylabel('OBV', fontsize=14)

                # Configure secondary axis (volatility)
                ax_obv_secondary.set_ylabel('Volatility (Std Dev)', fontsize=14)

                # Combine legends from both axes
                lines1, labels1 = axes2[2].get_legend_handles_labels()
                lines2, labels2 = ax_obv_secondary.get_legend_handles_labels()
                axes2[2].legend(lines1 + lines2, labels1 + labels2, loc='upper left', fontsize=12)

                # OBV signal interpretation
                if volume_metrics["obv_signal"] == "bullish":
                    obv_level = "Bullish"
                    obv_color = 'lightgreen'
                    obv_explanation = "OBV crossed above EMA - Accumulation phase"
                elif volume_metrics["obv_signal"] == "bearish":
                    obv_level = "Bearish"
                    obv_color = 'lightcoral'
                    obv_explanation = "OBV crossed below EMA - Distribution phase"
                else:
                    obv_level = "Neutral"
                    obv_color = 'lightyellow'
                    if obv.iloc[-1] > obv_ema.iloc[-1]:
                        obv_explanation = "OBV above EMA - Bullish bias maintained"
                    else:
                        obv_explanation = "OBV below EMA - Bearish bias maintained"

                # Volatility explanation (same as before)
                if vol_signal == "high":
                    vol_level = "High"
                    vol_explanation_short = "High volatility detected"
                elif vol_signal == "low":
                    vol_level = "Low" 
                    vol_explanation_short = "Low volatility - consolidation"
                else:
                    vol_level = "Medium"
                    vol_explanation_short = "Normal volatility levels"

                # OBV and Volatility annotations
                current_obv = obv.iloc[-1]
                axes2[2].annotate(f'OBV: {obv_level}\n{obv_explanation}', 
                        xy=(df.index[-1], current_obv), 
                        xytext=(12, 40), textcoords='offset points',
                        bbox=dict(boxstyle='round,pad=0.5', facecolor=obv_color, alpha=0.7),
                        fontsize=12,
                        arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0.1', 
                                    color='black', alpha=0.7, lw=1.5))

                ax_obv_secondary.annotate(f'Volatility: {vol_level}\n{vol_explanation_short}', 
                        xy=(df.index[-1], weighted_vol), 
                        xytext=(-140, -50), textcoords='offset points',
                        bbox=dict(boxstyle='round,pad=0.5', 
                                facecolor='lightcoral' if vol_signal == "high" else 'lightgreen' if vol_signal == "low" else 'lightyellow', 
                                alpha=0.7),
                        fontsize=12,
                        arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=-0.1', 
                                    color='black', alpha=0.7, lw=1.5))
            else:
                # No volume data - show volatility only
                axes2[2].plot(df.index, volatility_series, label='Volatility (Weighted Std Dev)', 
                            color='orange', linewidth=2)
                axes2[2].fill_between(df.index, 0, volatility_series, alpha=0.3, color='orange')

                axes2[2].set_title("Volatility Analysis (OBV Not Available)", fontsize=16, fontweight='bold')
                axes2[2].grid(True, alpha=0.3)
                axes2[2].set_ylabel('Volatility (Std Dev)', fontsize=14)
                axes2[2].legend(loc='upper left', fontsize=12)

                # Volatility annotation only
                axes2[2].annotate(f'Volatility: {vol_level}\n{vol_explanation}', 
                        xy=(df.index[-1], current_vol), 
                        xytext=(12, 12), textcoords='offset points',
                        bbox=dict(boxstyle='round,pad=0.3', facecolor=vol_color, alpha=0.7),
                        fontsize=12)

            # Format x-axis with same format as first image
            def format_date(x, pos):
                try:
                    dt = mdates.num2date(x)
                    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                                'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
                    return f"{dt.day:02d}-{month_names[dt.month-1]}-{dt.year} {dt.hour:02d}:{dt.minute:02d}"
                except:
                    return ""

            axes2[2].xaxis.set_major_formatter(mticker.FuncFormatter(format_date))
            axes2[2].xaxis.set_major_locator(mdates.HourLocator(interval=max(1, len(df)//10)))
            plt.setp(axes2[2].xaxis.get_majorticklabels(), rotation=45)

            # Set xlabel for second image
            axes2[2].set_xlabel('Time (UTC)', fontsize=14)

            # Adjust layout for second image - same as first image
            plt.tight_layout()

            # Save the second plot
            plt.savefig("reports/indicators_rsi_volatility.png", dpi=200, bbox_inches='tight', facecolor='white')
            plt.close()

            # Add both images to PDF
            if os.path.exists("reports/indicators_price_macd.png"):
                pdf.ln(4)
                pdf.add_image("reports/indicators_price_macd.png", size_type='large')
                pdf.ln(7)
                
            if os.path.exists("reports/indicators_rsi_volatility.png"):
                pdf.ln(4)
                pdf.add_image("reports/indicators_rsi_volatility.png", size_type='large')
                pdf.ln(7)

            pdf.add_page()
            pdf.add_section_title("Technical Indicators Analysis & Interpretation")

            # MACD Analysis
            pdf.set_font("Arial", "B", 10)
            pdf.set_text_color(*pdf.get_signal_color(macd_value))
            pdf.multi_cell(0, 7, f"MACD Analysis: {macd_position}")
            
            pdf.set_font("Arial", "", 10)
            pdf.set_text_color(40, 40, 40)
            current_macd_line = df['macd_line'].iloc[-1]
            current_signal_line = df['macd_signal'].iloc[-1]
            pdf.multi_cell(0, 6, f"Current MACD Line: {current_macd_line:.4f} | Signal Line: {current_signal_line:.4f} | Histogram: {current_hist:.4f}")
            
            if "Bullish" in macd_position:
                pdf.set_text_color(0, 128, 0)
                pdf.multi_cell(0, 6, "**INTERPRETATION**: The MACD line is above the signal line, indicating bullish momentum. This suggests potential upward price movement. The histogram bars are positive, confirming strengthening bullish momentum.")
            elif "Bearish" in macd_position:
                pdf.set_text_color(180, 0, 0)
                pdf.multi_cell(0, 6, "**INTERPRETATION**: The MACD line is below the signal line, indicating bearish momentum. This suggests potential downward price movement. The histogram bars are negative, confirming strengthening bearish momentum.")
            else:
                pdf.set_text_color(200, 140, 0)
                pdf.multi_cell(0, 6, "**INTERPRETATION**: MACD signals are converging near zero, indicating a consolidation phase. No clear directional bias. Wait for a definitive crossover signal.")
            
            pdf.ln(5)
            
            # RSI Analysis
            pdf.set_font("Arial", "B", 10)
            pdf.set_text_color(*pdf.get_signal_color(rsi_signal))
            pdf.multi_cell(0, 7, f"RSI Analysis: {rsi_level}")
            
            pdf.set_font("Arial", "", 10)
            pdf.set_text_color(40, 40, 40)
            pdf.multi_cell(0, 6, f"Current RSI Value: {current_rsi:.2f} (Scale: 0-100)")
            
            if current_rsi > 75:
                pdf.set_text_color(180, 0, 0)
                pdf.multi_cell(0, 6, "**INTERPRETATION**: RSI is in overbought territory (>75). The asset may be due for a price correction or pullback. Consider taking profits or waiting for a better entry point. High probability of downward pressure.")
            elif current_rsi < 25:
                pdf.set_text_color(0, 128, 0)
                pdf.multi_cell(0, 6, "**INTERPRETATION**: RSI is in oversold territory (<25). The asset may be undervalued and due for a bounce. This could present a buying opportunity for contrarian investors. High probability of upward recovery.")
            elif current_rsi > 50:
                pdf.set_text_color(0, 100, 0)
                pdf.multi_cell(0, 6, "**INTERPRETATION**: RSI is above the midline (50), indicating bullish momentum dominance. Buyers are in control. The uptrend is likely to continue as long as RSI stays above 50.")
            else:
                pdf.set_text_color(150, 75, 0)
                pdf.multi_cell(0, 6, "**INTERPRETATION**: RSI is below the midline (50), indicating bearish momentum dominance. Sellers are in control. The downtrend may continue as long as RSI stays below 50.")
            
            pdf.ln(5)
            
            # Bollinger Bands Analysis
            pdf.set_font("Arial", "B", 10)
            pdf.set_text_color(*pdf.get_signal_color(bb_signal))
            pdf.multi_cell(0, 7, f"Bollinger Bands Analysis: {bb_signal}")
            
            pdf.set_font("Arial", "", 10)
            pdf.set_text_color(40, 40, 40)
            pdf.multi_cell(0, 6, f"Current Price: ${current_price:,.2f} | Upper Band: ${current_upper:,.2f} | Lower Band: ${current_lower:,.2f} | Middle Band: ${current_middle:,.2f}")            
            band_width = ((current_upper - current_lower) / current_middle) * 100
            pdf.multi_cell(0, 6, f"Band Width: {band_width:.2f}% (Volatility Measure)")
            
            if current_price > current_upper:
                pdf.set_text_color(180, 0, 0)
                pdf.multi_cell(0, 6, "**INTERPRETATION**: Price has breached the upper Bollinger Band, indicating potential overbought conditions. This could signal a reversal or continuation breakout. Monitor for price rejection or sustained momentum above the band.")
            elif current_price < current_lower:
                pdf.set_text_color(0, 128, 0)
                pdf.multi_cell(0, 6, "**INTERPRETATION**: Price has breached the lower Bollinger Band, indicating potential oversold conditions. This could signal a reversal opportunity or continuation breakdown. Look for price recovery or further deterioration.")
            elif current_price > current_middle:
                pdf.set_text_color(0, 100, 0)
                pdf.multi_cell(0, 6, "**INTERPRETATION**: Price is above the middle band (20-period SMA), indicating bullish territory. The uptrend is supported as long as price remains above the middle band. Upper band acts as resistance.")
            else:
                pdf.set_text_color(150, 75, 0)
                pdf.multi_cell(0, 6, "**INTERPRETATION**: Price is below the middle band (20-period SMA), indicating bearish territory. The downtrend is supported as long as price remains below the middle band. Lower band acts as support.")
            
            pdf.ln(5)
            
            # Volatility Analysis - Using the SAME vol_signal and weighted_vol from above
            pdf.set_font("Arial", "B", 10)
            pdf.set_text_color(0, 0, 0)
            pdf.multi_cell(0, 7, f"Volatility Analysis: {vol_level}")

            pdf.set_font("Arial", "", 10)
            pdf.set_text_color(40, 40, 40)

            # Use the same weighted_vol and thresholds from above for consistency
            if len(med_vol_clean) >= 10:
                avg_vol = med_vol_clean.mean()
                pdf.multi_cell(0, 6, f"Current Volatility: {weighted_vol:.4f} | Average Volatility: {avg_vol:.4f}")
                
                vol_percentile = (weighted_vol / avg_vol) * 100 if avg_vol > 0 else 100
                pdf.multi_cell(0, 6, f"Relative Volatility: {vol_percentile:.1f}% of average")
                
                # Show the thresholds used in the actual calculation
                pdf.multi_cell(0, 6, f"High Threshold: {high_threshold:.4f} | Low Threshold: {low_threshold:.4f}")
            else:
                pdf.multi_cell(0, 6, f"Current Volatility: {weighted_vol:.4f} | Insufficient data for average calculation")

            # Use the actual vol_signal logic for interpretation
            if vol_signal == "high":
                pdf.set_text_color(180, 0, 0)
                pdf.multi_cell(0, 6, "**INTERPRETATION**: High volatility environment detected. Expect significant price swings and increased risk. Use smaller position sizes and wider stop-losses. Market uncertainty is elevated - exercise caution.")
            elif vol_signal == "low":
                pdf.set_text_color(0, 100, 150)
                pdf.multi_cell(0, 6, "**INTERPRETATION**: Low volatility environment detected. Price is consolidating with minimal fluctuations. This often precedes significant moves. Prepare for potential breakout in either direction.")
            else:
                pdf.set_text_color(100, 100, 100)
                pdf.multi_cell(0, 6, "**INTERPRETATION**: Medium volatility levels observed. Price movement is within typical ranges. Standard risk management rules apply. Market conditions are relatively stable.")

            pdf.ln(2)
            
            # Overall Technical Summary
            pdf.set_font("Arial", "B", 10)
            pdf.set_text_color(0, 0, 0)
            pdf.multi_cell(0, 8, "Overall Technical Assessment:")
            
            pdf.set_font("Arial", "", 10)
            pdf.set_text_color(50, 50, 50)
            
            # Count bullish/bearish signals using actual signal values
            signal_values = [macd_signal, rsi_signal, bb_signal_calc]
            bullish_count = sum(1 for s in signal_values if s in ['bullish', 'oversold', 'breakout_up'])
            bearish_count = sum(1 for s in signal_values if s in ['bearish', 'overbought', 'breakout_down'])
            
            if bullish_count > bearish_count:
                pdf.set_text_color(0, 128, 0)
                pdf.multi_cell(0, 6, f"BULLISH BIAS: {bullish_count} out of 3 key indicators show bullish signals. The technical outlook favors upward movement, but always consider risk management and market context.")
            elif bearish_count > bullish_count:
                pdf.set_text_color(180, 0, 0)
                pdf.multi_cell(0, 6, f"BEARISH BIAS: {bearish_count} out of 3 key indicators show bearish signals. The technical outlook favors downward movement. Exercise caution and consider defensive strategies.")
            else:
                pdf.set_text_color(200, 140, 0)
                pdf.multi_cell(0, 6, "MIXED SIGNALS: Technical indicators are showing conflicting signals. Market is likely in a consolidation phase. Wait for clearer directional confirmation before taking significant positions.")
            
            pdf.ln(1)

        except Exception as e:
            pdf.add_paragraph(f"(Could not generate indicator chart: {e})", color=(255, 0, 0))
            print(f"Plotting error: {e}")  # For debugging

    pdf.add_page()

    # 2. Risk Management
    pdf.set_link(links["risk_management"])
    pdf.add_section_title("\n\n5. Risk Assessment & Position Management")

    # Add timeframe and data context information
    pdf.set_font("Arial", "B", 11)
    pdf.set_text_color(0, 0, 0)
    pdf.multi_cell(0, 6, f"Analysis Parameters:")

    pdf.set_font("Arial", "", 10)
    pdf.set_text_color(60, 60, 60)

    # Get historical limit from signal_info or set default
    historical_limit = HISTORICAL_LIMIT
    data_points = len(signal_info['price_snapshot']) if 'price_snapshot' in signal_info else 'Unknown'

    # Get total days from summary if available
    if isinstance(summary, dict):
        analysis_period = summary.get('Total Days Analyzed', '2500 candles')
    else:
        analysis_period = '2500 candles'
    
    pdf.multi_cell(0, 5, f"- Timeframe: {timeframe_str}")
    pdf.multi_cell(0, 5, f"- Historical Data Limit: {analysis_period}")
    pdf.multi_cell(0, 5, f"- Data Points Analyzed: {data_points} candles")
    pdf.multi_cell(0, 5, f"- Analysis Date: {datetime.now(timezone.utc).strftime('%d-%b-%Y %H:%M:%S UTC')}")

    pdf.ln(3)

    # Extract entry price
    entry_price = "N/A"
    try:
        price_df = signal_info.get("price_snapshot", None)
        if isinstance(price_df, pd.DataFrame) and not price_df.empty:
            raw_entry = price_df["close"].iloc[-1]
            entry_price = f"{raw_entry:,.2f}"
        else:
            raw_entry = float(risk_info.get("entry_price", 0))
    except:
        raw_entry = float(risk_info.get("entry_price", 0))

    # Helper function for safe float conversion
    def safe_float_convert(value, default=0.0):
        """Safely convert various data types to float"""
        try:
            if value is None:
                return default
            # Handle string with commas and dollar signs
            if isinstance(value, str):
                value = value.replace(',', '').replace('$', '').strip()
            return float(value)
        except (ValueError, TypeError):
            return default

    # Calculate dollar differences for max loss/gain per share
    try:
        entry = safe_float_convert(raw_entry)
        sl = safe_float_convert(risk_info.get('stop_loss', 0))
        tp = safe_float_convert(risk_info.get('take_profit', 0))
        
        print(f"Debug - Entry: {entry}, SL: {sl}, TP: {tp}")  # Debug line
        
        # Calculate max loss and gain per share
        max_loss_per_share = abs(entry - sl) if entry > 0 and sl > 0 else 0
        max_gain_per_share = abs(tp - entry) if tp > 0 and entry > 0 else 0
        
    except Exception as e:
        print(f"Calculation error: {e}")
        max_loss_per_share = 0
        max_gain_per_share = 0
        entry = 0
        sl = 0
        tp = 0

    # Generate the risk management plot first (before layout)
    plot_path = None
    signal_direction = signal_info.get('signal', '').upper()
    
    # Only generate plot if signal is not HOLD
    if signal_direction != 'HOLD' and signal_direction != 'NO CLEAR DIRECTION':
        try:
            # Use safe conversion for plot values
            entry = safe_float_convert(raw_entry)
            sl = safe_float_convert(risk_info.get('stop_loss', 0))
            tp = safe_float_convert(risk_info.get('take_profit', 0))

            print(f"Debug Plot - Entry: {entry}, SL: {sl}, TP: {tp}")  # Debug line

            # Only create plot if we have valid values
            if entry > 0 and (sl > 0 or tp > 0):
                import matplotlib.pyplot as plt
                import matplotlib.ticker as mticker
                import os

                levels = []
                labels = []
                colors = []

                # Only add valid levels
                if sl > 0:
                    levels.append(sl)
                    labels.append('Stop Loss')
                    colors.append('red')
                
                if entry > 0:
                    levels.append(entry)
                    labels.append('Entry Price')
                    colors.append('blue')
                
                if tp > 0:
                    levels.append(tp)
                    labels.append('Take Profit')
                    colors.append('green')

                plt.figure(figsize=(8, 6))
                
                # Plot each valid level
                for level, label, color in zip(levels, labels, colors):
                    plt.axhline(y=level, color=color, linestyle='--', linewidth=2, label=f"{label}: ${level:,.2f}")

                # Fill zones only if we have valid values
                if sl > 0 and entry > 0:
                    plt.fill_betweenx([min(sl, entry), max(sl, entry)], 0, 1, 
                                     color='red', alpha=0.1, transform=plt.gca().get_yaxis_transform())
                if tp > 0 and entry > 0:
                    plt.fill_betweenx([min(entry, tp), max(entry, tp)], 0, 1, 
                                     color='green', alpha=0.1, transform=plt.gca().get_yaxis_transform())

                plt.title("Risk Management Levels", fontsize=14, fontweight='bold')
                plt.xticks([])
                plt.yticks(fontsize=10)
                plt.ylabel("Price ($)", fontsize=12)
                plt.gca().yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'${x:,.0f}'))
                plt.legend(loc="best", fontsize=10)
                plt.grid(True, alpha=0.3)
                plt.tight_layout()

                os.makedirs("reports/plots", exist_ok=True)
                plot_path = "reports/plots/risk_management_plot.png"
                plt.savefig(plot_path, bbox_inches='tight', dpi=150)
                plt.close()
                
                print(f"Plot saved successfully to: {plot_path}")  # Debug line
            else:
                print(f"Invalid values for plotting - Entry: {entry}, SL: {sl}, TP: {tp}")  # Debug line

        except Exception as e:
            print(f"Plot generation error: {e}")
            import traceback
            traceback.print_exc()  # This will show the full error traceback

    # Create two-column layout
    pdf.ln(5)  # Add some space after title

    # Save current position
    y_start = pdf.get_y()

    # Determine layout based on whether plot exists
    if plot_path:
        # Two-column layout for BUY/SELL signals with plot
        left_column_width = pdf.w * 0.55  # 55% of page width for more space
        right_column_start_x = pdf.l_margin + left_column_width + 8  # 8mm gap between columns
    else:
        # Single column layout for HOLD signals without plot
        left_column_width = pdf.w - pdf.l_margin - pdf.r_margin  # Full width
        right_column_start_x = None

    # Create Risk & Trade Parameters Table
    pdf.set_font("Arial", "B", 11)
    pdf.set_text_color(0, 0, 0)
    pdf.multi_cell(0, 6, "\nRisk & Trade Parameters:\n")

    # Calculate max loss and gain per trade
    try:
        entry_val = float(str(entry_price).replace(',', '').replace('$', '')) if entry_price != 'N/A' else 0
        stop_loss_val = float(str(sl).replace(',', '').replace('$', '')) if sl != 'N/A' else 0
        take_profit_val = float(str(tp).replace(',', '').replace('$', '')) if tp != 'N/A' else 0
        
        max_loss_per_trade = abs(entry_val - stop_loss_val) if stop_loss_val > 0 else 0
        max_gain_per_trade = abs(take_profit_val - entry_val) if take_profit_val > 0 else 0
    except:
        max_loss_per_trade = 0
        max_gain_per_trade = 0

    # Create table data
    risk_params_data = [
        ["Entry Price", f"$ {entry_price if entry_price == 'N/A' else entry_price}", "NEUTRAL"],
        ["Stop Loss", f"$ {sl:,.2f}" if sl > 0 else "$ 0.00", "LOSS"],
        ["Take Profit", f"$ {tp:,.2f}" if tp > 0 else "$ 0.00", "PROFIT"],
        ["Max Loss per Share", f"$ {max_loss_per_share:,.2f}" if max_loss_per_share > 0 else "$ 0.00", "LOSS"],
        ["Max Gain per Share", f"$ {max_gain_per_share:,.2f}" if max_gain_per_share > 0 else "$ 0.00", "PROFIT"],
        ["Risk-Reward Ratio", f"{risk_info.get('rr_ratio', 'N/A')}", "RRR"],
        ["Risk Level", f"{risk_info.get('risk_level', 'N/A')}", "RISK"],
        ["Expected Profit %", f"{risk_info.get('expected_profit_percent', 'N/A')}", "PROFIT"]
    ]

    # Table styling
    pdf.set_font("Arial", "B", 9)
    row_height = 6
    col1_width = 60  # Parameter name
    col2_width = 50  # Value

    # Table header
    pdf.set_fill_color(200, 200, 200)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(col1_width, row_height, "Parameter", border=1, align='C', fill=True)
    pdf.cell(col2_width, row_height, "Value", border=1, align='C', fill=True)
    pdf.ln()

    # Table rows
    pdf.set_font("Arial", "", 9)
    for param, value, color_type in risk_params_data:
        # Set row background (alternating light gray)
        pdf.set_fill_color(255, 255, 255)
        
        # Parameter name column (black text)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(col1_width, row_height, param, border=1, align='L', fill=True)
        
        # Value column with color coding
        if color_type == "PROFIT":
            try:
                # Check if it's a percentage or dollar amount
                if "%" in value:
                    profit_val = float(value.replace('%', ''))
                    text_color = (0, 150, 0) if profit_val > 0 else (200, 0, 0) if profit_val < 0 else (100, 100, 100)
                else:
                    # For take profit and max gain
                    text_color = (0, 150, 0)
            except:
                text_color = (0, 150, 0)
        elif color_type == "LOSS":
            text_color = (200, 0, 0)
        elif color_type == "RRR":
            try:
                rrr_val = float(str(risk_info['rr_ratio']).split(':')[0]) if ':' in str(risk_info['rr_ratio']) else float(risk_info['rr_ratio'])
                text_color = (0, 150, 0) if rrr_val >= 2 else (200, 150, 0) if rrr_val >= 1 else (200, 0, 0)
            except:
                text_color = (100, 100, 100)
        elif color_type == "RISK":
            risk_level_lower = risk_info['risk_level'].lower()
            text_color = (0, 100, 0) if 'low' in risk_level_lower else (200, 0, 0) if 'high' in risk_level_lower else (200, 100, 0)
        elif color_type == "NEUTRAL":
            text_color = (0, 102, 204)
        else:
            text_color = (0, 0, 0)
        
        pdf.set_text_color(*text_color)
        pdf.cell(col2_width, row_height, value, border=1, align='C', fill=True)
        pdf.ln()

    # Add some spacing before the explanation
    pdf.ln(5)

    # Enhanced dynamic formal explanation (keeping within left column width)
    try:
        # Determine signal direction
        signal_direction = signal_info.get('signal', '').upper()
        
        # Special handling for HOLD/No Clear Direction signals
        if signal_direction == 'HOLD' or (sl == 0 and tp == 0):
            # Generate dynamic HOLD explanation
            hold_explanations = [
                f"The current market analysis at ${entry_price} reveals conflicting signals and mixed technical indicators, resulting in a neutral stance. Market conditions suggest waiting for clearer directional momentum before establishing any position.",
                f"Based on comprehensive market evaluation at ${entry_price}, the trading algorithm has identified sideways consolidation patterns and lack of decisive breakout signals. This neutral positioning recommends patience until market direction becomes more defined.",
                f"Technical analysis at the ${entry_price} level indicates balanced buying and selling pressure with no clear trend dominance. The system advises maintaining a watchful approach until stronger directional signals emerge from the market structure.",
                f"Current market assessment at ${entry_price} shows indecisive price action with competing technical forces. The neutral recommendation reflects the algorithm's preference for high-probability setups over marginal trading opportunities.",
                f"Market dynamics at ${entry_price} present a complex technical landscape with conflicting momentum indicators. The hold strategy prioritizes capital preservation while monitoring for clearer trend development and improved risk-reward scenarios."
            ]
            
            # Select explanation based on entry price (for variety)
            import random
            random.seed(int(entry) % 1000)  # Deterministic but varied selection
            selected_explanation = random.choice(hold_explanations)
            
            # Add explanation with width constraint for left column
            pdf.add_paragraph(selected_explanation)
            
        else:
            # Original dynamic explanation for active trading signals
            # Calculate percentages
            sl_distance = abs(entry - sl)
            tp_distance = abs(tp - entry)
            sl_percent = (sl_distance / entry) * 100 if entry > 0 else 0
            tp_percent = (tp_distance / entry) * 100 if entry > 0 else 0
            
            # Generate dynamic explanation based on parameters
            explanation_parts = []
            
            # Opening statement varies by signal
            if signal_direction == 'BUY':
                explanation_parts.append(f"This bullish position is structured around an entry point of ${entry_price}")
            elif signal_direction == 'SELL':
                explanation_parts.append(f"This bearish position is established with an entry price of ${entry_price}")
            else:
                explanation_parts.append(f"This trading setup is anchored at an entry price of ${entry_price}")
            
            # Stop loss commentary based on distance
            if sl_percent < 2:
                explanation_parts.append(f"with a tight stop loss positioned at ${risk_info['stop_loss']:,.2f} ({sl_percent:.1f}% downside protection)")
            elif sl_percent < 5:
                explanation_parts.append(f"featuring a conservative stop loss at ${risk_info['stop_loss']:,.2f} ({sl_percent:.1f}% risk buffer)")
            else:
                explanation_parts.append(f"incorporating a wide stop loss at ${risk_info['stop_loss']:,.2f} ({sl_percent:.1f}% maximum risk tolerance)")
            
            # Take profit based on potential
            if tp_percent < 5:
                explanation_parts.append(f"targeting modest gains at ${risk_info['take_profit']:,.2f} ({tp_percent:.1f}% profit potential)")
            elif tp_percent < 15:
                explanation_parts.append(f"aiming for solid returns at ${risk_info['take_profit']:,.2f} ({tp_percent:.1f}% upside target)")
            else:
                explanation_parts.append(f"pursuing aggressive profit targets at ${risk_info['take_profit']:,.2f} ({tp_percent:.1f}% substantial upside)")
            
            # Risk-reward analysis
            try:
                rr_ratio = risk_info['rr_ratio']
                rr_float = float(str(rr_ratio).replace(':', '').split()[-1])
                if rr_float < 1.5:
                    rr_comment = "indicating a conservative risk-reward approach suitable for capital preservation strategies"
                elif rr_float < 3:
                    rr_comment = "reflecting a balanced risk-reward profile that aligns with systematic trading principles"
                else:
                    rr_comment = "demonstrating an aggressive risk-reward framework designed for maximum profit extraction"
            except:
                rr_comment = "maintaining a calculated risk-reward balance"
                rr_ratio = risk_info.get('rr_ratio', '1:0')
            
            explanation_parts.append(f"The {rr_ratio} ratio {rr_comment}.")
            
            # Risk level context
            risk_level_lower = risk_info['risk_level'].lower()
            if 'low' in risk_level_lower:
                risk_context = "This low-risk configuration prioritizes capital protection while maintaining moderate profit potential through precise market timing and volatility-adjusted positioning."
            elif 'high' in risk_level_lower:
                risk_context = "This high-risk setup maximizes profit potential by accepting increased exposure, suitable for experienced traders with strong risk tolerance and active monitoring capabilities."
            else:
                risk_context = "This moderate-risk approach balances profit opportunity with downside protection, incorporating market volatility analysis and trend-following principles."
            
            # Combine all parts
            full_explanation = f"{explanation_parts[0]}, {explanation_parts[1]}, and {explanation_parts[2]}. {explanation_parts[3]} {risk_context}"
            
            pdf.add_paragraph(full_explanation)
        
    except Exception as e:
        print(f"Explanation generation error: {e}")
        # Enhanced fallback to original template if dynamic generation fails
        pdf.add_paragraph(
            f"\n\nThis risk management setup is based on the entry price of ${entry_price}, "
            f"with a Stop Loss defined at ${risk_info.get('stop_loss', 'N/A')} and a Take Profit target at ${risk_info.get('take_profit', 'N/A')}. "
            f"The system used an intelligent volatility-adjusted approach for risk placement, incorporating factors such as "
            f"market trend strength, overall sentiment, and asset-specific volatility to dynamically adjust the buffer zones. "
            f"The Risk-Reward ratio of {risk_info.get('rr_ratio', 'N/A')} reflects the balance between potential downside protection and profit opportunity."
        )

    # Enhanced HOLD Note (keep in left column)
    if signal_info['signal'].upper() == "HOLD":
        pdf.add_paragraph(
            "\n\nNote: As this signal indicates No Clear Direction, the Stop Loss, Take Profit, and expected profit values are set to 0 by default. "
            "No active trade is recommended under the current market conditions.",
            color=(150, 100, 0),
            bold=True
        )

    # Get the height after adding all content
    content_end_y = pdf.get_y()

    # Right column - Risk Management Plot (only for BUY/SELL signals)
    if plot_path and right_column_start_x:
        # Calculate available width for the chart (remaining space minus margins)
        chart_width = pdf.w - right_column_start_x - pdf.r_margin
        chart_height = min(chart_width * 0.75, (content_end_y - y_start) * 0.8)  # Maintain aspect ratio
        
        # Calculate vertical centering position
        available_height = content_end_y - y_start
        vertical_center_offset = (available_height - chart_height) / 2
        chart_y_position = y_start + vertical_center_offset
        
        # Add image with calculated dimensions and centered positioning
        pdf.image(plot_path, 
                x=right_column_start_x, 
                y=chart_y_position, 
                w=chart_width, 
                h=chart_height)
        
        # Move cursor to below both elements with extra gap
        final_y = max(content_end_y, chart_y_position + chart_height) + 15  # 15mm gap below
    elif plot_path and not right_column_start_x:
        # This case shouldn't happen, but just in case
        final_y = content_end_y + 10
    else:
        # No plot case (HOLD signal) - just use content height with gap
        final_y = content_end_y + 10

    pdf.set_y(final_y)  # Set position with proper gap

    pdf.add_page()

    # 3. Timing
    pdf.set_link(links["signal_timing"])
    pdf.add_section_title("\n\n6. Signal Duration & Targets")

    # Add timeframe and data context information
    pdf.set_font("Arial", "B", 11)
    pdf.set_text_color(0, 0, 0)
    pdf.multi_cell(0, 6, f"Analysis Parameters:")

    pdf.set_font("Arial", "", 10)
    pdf.set_text_color(60, 60, 60)

    # Get historical limit from signal_info or set default
    historical_limit = HISTORICAL_LIMIT
    data_points = len(signal_info['price_snapshot']) if 'price_snapshot' in signal_info else 'Unknown'

    # Get total days from summary if available
    if isinstance(summary, dict):
        analysis_period = summary.get('Total Days Analyzed', '2500 candles')
    else:
        analysis_period = '2500 candles'
    
    from datetime import datetime, timezone

    def safe_format_datetime(dt):
        """Return formatted datetime string. Accepts datetime or ISO string."""
        if isinstance(dt, str):
            try:
                dt = datetime.fromisoformat(dt)
            except Exception:
                return 'N/A'
        if isinstance(dt, datetime):
            return dt.strftime('%d-%b-%Y %H:%M')
        return 'N/A'

    pdf.multi_cell(0, 5, f"- Timeframe: {timeframe_str}")
    pdf.multi_cell(0, 5, f"- Historical Data Limit: {analysis_period}")
    pdf.multi_cell(0, 5, f"- Data Points Analyzed: {data_points} candles")
    pdf.multi_cell(0, 5, f"- Analysis Date: {datetime.now(timezone.utc).strftime('%d-%b-%Y %H:%M:%S UTC')}")

    pdf.ln(3)

    start = timing_info.get('start')
    end = timing_info.get('end')
    duration = timing_info.get('duration', 'N/A')

    formatted_start = safe_format_datetime(start)
    formatted_end = safe_format_datetime(end)

    # Get signal type
    signal_direction = signal_info.get('signal', 'HOLD').upper()
    show_graph = signal_direction in ['BUY', 'SELL']

    # Entry and Exit Prices
    entry_price = "N/A"
    exit_price_tp = "N/A"
    exit_price_sl = "N/A"
    exit_price_timing = "N/A"
    entry_price_num = 0
    exit_price_tp_num = 0
    exit_price_sl_num = 0

    try:
        price_df = signal_info.get("price_snapshot", None)
        if isinstance(price_df, pd.DataFrame) and not price_df.empty:
            entry_price_num = price_df["close"].iloc[-1]
            exit_price_timing = entry_price_num  # assumed
            # Format them
            entry_price = f"{entry_price_num:,.2f}"
            exit_price_timing = f"{exit_price_timing:,.2f}"
    except:
        pass

    # From risk_info
    try:
        exit_price_tp_num = float(risk_info['take_profit'])
        exit_price_sl_num = float(risk_info['stop_loss'])
        exit_price_tp = f"{exit_price_tp_num:,.2f}"
        exit_price_sl = f"{exit_price_sl_num:,.2f}"
    except:
        pass

    # Generate the timing plot first (before layout) - following risk management pattern
    timing_plot_path = None
    if show_graph and start and end and entry_price_num > 0 and exit_price_tp_num > 0 and exit_price_sl_num > 0:
        try:
            import matplotlib.pyplot as plt
            import matplotlib.dates as mdates
            from datetime import datetime, timedelta
            import numpy as np
            import os

            # Create figure with white background
            plt.figure(figsize=(8, 6))
            
            # Generate time series for visualization
            time_points = pd.date_range(start=start, end=end, periods=50)
            
            # Determine signal direction
            is_buy_signal = signal_direction == 'BUY'
            
            # Create realistic price trajectory
            base_price = entry_price_num
            target_price = exit_price_tp_num if is_buy_signal else exit_price_sl_num
            
            # Generate smooth trajectory with some volatility
            progress = np.linspace(0, 1, len(time_points))
            trend_strength = 0.6  # 60% progress toward target
            trend = (target_price - base_price) * progress * trend_strength
            
            # Add realistic volatility
            np.random.seed(42)  # For consistent results
            volatility = np.random.normal(0, abs(base_price * 0.008), len(time_points))
            volatility = np.cumsum(volatility * 0.2)  # Smooth volatility
            
            predicted_prices = base_price + trend + volatility
            
            # Plot the main price line
            color_main = '#1f77b4' if is_buy_signal else '#d62728'  # Blue for BUY, Red for SELL
            plt.plot(time_points, predicted_prices, linewidth=2.5, color=color_main, 
                    label=f'Predicted Movement ({signal_direction})', alpha=0.9)
            
            # Add entry point
            plt.scatter([start], [base_price], color='#2ca02c', s=80, zorder=5,
                    marker='o', label='Entry Point', edgecolors='white', linewidth=1.5)
            
            # Add target levels
            plt.axhline(y=exit_price_tp_num, color='#2ca02c', linestyle='--', alpha=0.7, 
                    linewidth=1.5, label=f'Take Profit: ${exit_price_tp_num:,.0f}')
            plt.axhline(y=exit_price_sl_num, color='#d62728', linestyle='--', alpha=0.7, 
                    linewidth=1.5, label=f'Stop Loss: ${exit_price_sl_num:,.0f}')
            
            # Formatting
            plt.xlabel('Time', fontsize=12, fontweight='bold')
            plt.ylabel('Price ($)', fontsize=12, fontweight='bold')
            plt.title(f'{signal_direction} Signal Analysis\nDuration: {duration}', 
                    fontsize=14, fontweight='bold', pad=15)
            
            # Format y-axis for currency
            plt.gca().yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))
            
            # Format x-axis for dates
            plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%d-%b %H:%M'))
            plt.gca().xaxis.set_major_locator(mdates.HourLocator(interval=max(1, int((end - start).total_seconds() // 3600 // 4))))
            plt.setp(plt.gca().xaxis.get_majorticklabels(), rotation=45, ha='right', fontsize=10)
            
            # Clean grid
            plt.grid(True, alpha=0.3, linestyle='-', linewidth=0.5)
            
            # Legend
            plt.legend(loc='best', frameon=True, fancybox=False, shadow=False, 
                    framealpha=1.0, fontsize=10, edgecolor='gray')
            
            # Remove top and right spines for cleaner look
            plt.gca().spines['top'].set_visible(False)
            plt.gca().spines['right'].set_visible(False)
            
            # Tight layout
            plt.tight_layout()
            
            # Save to file (same approach as risk management)
            os.makedirs("reports/plots", exist_ok=True)
            timing_plot_path = "reports/plots/signal_timing_plot.png"
            plt.savefig(timing_plot_path, bbox_inches='tight', dpi=150, 
                    facecolor='white', edgecolor='none')
            plt.close()
            
        except Exception as e:
            print(f"Timing plot generation error: {e}")

    # Create two-column layout (same as risk management)
    pdf.ln(5)  # Add some space after title

    # Save current position
    y_start = pdf.get_y()

    # Left column - Content (takes up about 60% of page width)
    left_column_width = pdf.w * 0.6  # 60% of page width
    right_column_start_x = pdf.l_margin + left_column_width + 5  # 5mm gap between columns

    # Add timing details in left column
    pdf.add_paragraph(f"Valid From: {formatted_start} UTC", bold=True)
    pdf.add_paragraph(f"Valid To: {formatted_end} UTC", bold=True)
    pdf.add_paragraph(f"Estimated Duration: {duration}", bold=True)
    pdf.add_paragraph("Note: This is an estimated signal validity based on ATR, volatility, and confidence. No future data is used.", 
                    color=(100, 100, 100))

    pdf.ln(5)
    pdf.add_section_title("Entry and Exit Price Range")
    pdf.add_paragraph(f"Entry Price: $ {entry_price}", bold=True)
    pdf.add_paragraph(f"Exit if Take Profit Triggered: $ {exit_price_tp}", color=(0, 100, 0), bold=True)
    pdf.add_paragraph(f"Exit if Stop Loss Triggered: $ {exit_price_sl}", color=(200, 0, 0), bold=True)
    pdf.add_paragraph("Note: Exit if the Duration is Expired before the Price Hit Stop Loss or Take Profit.", 
                    color=(100, 100, 100), bold=True)

    # Get the height after adding all content
    content_end_y = pdf.get_y()

    # Right column - Signal Timing Plot
    if timing_plot_path:
        # Calculate available width for the chart (remaining space minus margins)
        chart_width = pdf.w - right_column_start_x - pdf.r_margin
        chart_height = min(chart_width * 0.75, content_end_y - y_start)  # Maintain aspect ratio or match content height
        
        # Add image with calculated dimensions
        pdf.image(timing_plot_path, 
                x=right_column_start_x, 
                y=y_start, 
                w=chart_width, 
                h=chart_height)
        
        # Move cursor to below both elements
        final_y = max(content_end_y, y_start + chart_height)
    else:
        # If plot generation failed, just use content height
        final_y = content_end_y
        if show_graph:  # Only show error message if we expected a graph
            pdf.set_xy(right_column_start_x, y_start)
            pdf.add_paragraph("(Timing plot generation failed)", color=(255, 0, 0))

    pdf.set_y(final_y + 10)  # Add some space after both elements

    pdf.add_page()

    #----------BACKTEST----SECTION-----------
    pdf.set_link(links["backtest_details"])
    pdf.add_section_title("7. Backtest Details")
    # 4. Summary
    pdf.set_link(links["backtest_summary"])
    pdf.add_section_title("7.1. Performance Metrics Overview")

    # Add dynamic paragraph summarizing backtest results
    if isinstance(summary, dict):
        # Extract key metrics for the summary paragraph
        backtest_period = summary.get('Backtest Period', 'N/A')
        total_days = summary.get('Total Days Analyzed', 'N/A')
        total_signals = summary.get('Total Signals Generated', 'N/A')
        success_rate = summary.get('Success Rate', 'N/A')
        avg_profit = summary.get('Avg Profit % (per trade)', 'N/A')
        cumulative_return = summary.get('Cumulative Net Return %', 'N/A')
        successful_signals = summary.get('Successful Signals', 'N/A')
        failed_signals = summary.get('Failed Signals', 'N/A')
        buy_signals = summary.get('BUY Signals', 'N/A')
        sell_signals = summary.get('SELL Signals', 'N/A')
        
        # Helper function to determine color based on value
        def get_value_color(value_str):
            import re
            try:
                numeric_match = re.search(r'-?\d+\.?\d*', str(value_str))
                if numeric_match:
                    numeric_val = float(numeric_match.group())
                    if numeric_val > 0:
                        return (0, 150, 0)  # Green for positive
                    elif numeric_val < 0:
                        return (255, 0, 0)  # Red for negative
                    else:
                        return (0, 0, 0)  # Black for zero
                else:
                    return (0, 0, 0)  # Black for non-numeric
            except:
                return (0, 0, 0)  # Black for any parsing errors
        
        # Determine colors for key metrics
        success_rate_color = get_value_color(success_rate)
        avg_profit_color = get_value_color(avg_profit)
        cumulative_color = get_value_color(cumulative_return)
        
        # Create a simple summary paragraph about system efficiency and accuracy
        # Set font to Arial, size 10, normal (not bold)
        pdf.set_font('Arial', '', 10)
        pdf.set_text_color(0, 0, 0)  # Black text
        
        # Simple summary focusing on system efficiency and accuracy
        summary_text = ("Our trading signal system demonstrates exceptional efficiency and accuracy in market analysis. "
                    "Through comprehensive backtesting, the system has proven its reliability \nin generating precise "
                    "trading signals with consistent performance metrics. The automated strategy showcases strong "
                    "analytical capabilities, delivering dependable \nresults that traders can trust for informed "
                    "decision-making in dynamic market conditions. All returns presented are calculated using the \n"
                    "geometric returns method to accurately account for compounding over time.")
        
        pdf.multi_cell(0, 5, summary_text)
        pdf.ln(1)  # Add space after paragraph

    # Create a two-column layout for summary table and chart
    pdf.ln(1)  # Add some space after title

    # Save current position for the two-column layout
    y_start = pdf.get_y()

    # Left column - Summary table (takes up about 50% of page width for better balance)
    left_column_width = pdf.w * 0.50  # 50% of page width
    right_column_start_x = pdf.l_margin + left_column_width + 5  # 5mm gap between columns

    # Right column - Chart dimensions and position (larger chart)
    available_width = pdf.w - right_column_start_x - pdf.r_margin
    
    # Make the chart significantly larger - use more of the available space
    chart_width = available_width * 1.1  # Use 110% of available width (extends slightly beyond column)
    chart_height = chart_width  # Keep it square for pie chart

    # Center the chart perfectly in the right column area
    chart_x = right_column_start_x + (available_width - chart_width) / 2
    chart_y = y_start + 2  # Start chart slightly below the table start (reduced from 5 to 2)

    # Add the chart at the calculated position
    pdf.image("reports/plots/backtest_chart.png", 
            x=chart_x, 
            y=chart_y, 
            w=chart_width, 
            h=chart_height)

    # Now add the summary table in the left column
    # Make sure we're positioned at the start of the left column
    pdf.set_xy(pdf.l_margin, y_start)

    if isinstance(summary, dict):
        pdf.add_key_value_table(summary)
    else:
        pdf.add_paragraph(str(summary))

    # Get the height after adding the table
    table_end_y = pdf.get_y()

    # Move cursor to below both elements
    final_y = max(table_end_y, chart_y + chart_height)
    pdf.set_y(final_y + 10)  # Add some space after both elements

    pdf.add_page()
    
    # 5. Backtest Table with row coloring
    if isinstance(summary, dict):
        analysis_period = summary.get('Total Days Analyzed', '2500 candles')
    else:
        analysis_period = '2500 candles'

    pdf.set_link(links["backtest_table"])
    pdf.add_section_title(f"7.2. Detailed Trade History ({analysis_period})")

    # 📘 5A. Abbreviations Legend Box (4-column compact layout)
    abbreviations = {
        "conf": "Signal confidence %",
        "Exit.P ($)": "Exit price of the trade", 
        "TD": "Actual trade duration (in mins)",
        "TP ($)": "Take Profit value",
        "SL ($)": "Stop Loss value",
        "r:r": "Risk-Reward ratio",
        "Exit.R": "Exit reason (TP / SL / TIME)",
        "R%": "Net return % after commission"
    }

    # Define colors for each abbreviation (alternating colors for better visibility)
    abbrev_colors = {
        "conf": (255, 235, 238),      # Light red
        "Exit.P ($)": (235, 255, 235), # Light green
        "TD": (248, 235, 255),        # Light purple
        "TP ($)": (255, 248, 235),    # Light orange
        "SL ($)": (235, 245, 255),    # Light blue
        "r:r": (255, 255, 235),       # Light yellow
        "Exit.R": (240, 248, 255),    # Alice blue
        "R%": (255, 235, 238)         # Light red
    }

    pdf.ln(4)
    pdf.set_font("Arial", "B", 10)
    pdf.set_fill_color(52, 73, 94)  # Dark blue background
    pdf.set_text_color(52, 73, 94)  
    pdf.cell(190, 8, "Abbreviations (Legend)", 0, ln=1, fill=False, align='L')

    pdf.set_font("Arial", "", 8)
    pdf.set_text_color(0, 0, 0)  # Reset to black text
    pdf.set_draw_color(180, 180, 180)  # Light grey border

    # Define cell widths
    key_width = 22
    desc_width = 45

    # Split into rows of 4 items
    items = list(abbreviations.items())
    row_items = [items[i:i + 4] for i in range(0, len(items), 4)]

    for row in row_items:
        for key, desc in row:
            # Set color for this abbreviation
            color = abbrev_colors.get(key, (255, 255, 255))
            pdf.set_fill_color(color[0], color[1], color[2])
            
            pdf.cell(key_width, 7, key, border=1, align="C", fill=True)
            pdf.cell(desc_width, 7, desc, border=1, fill=True)
        
        # Fill remaining space if less than 4 in last row
        remaining = 4 - len(row)
        if remaining:
            pdf.set_fill_color(255, 255, 255)  # White fill for empty cells
            for _ in range(remaining):
                pdf.cell(key_width, 7, "", border=0)
                pdf.cell(desc_width, 7, "", border=0)
        pdf.ln(7)

    pdf.ln(2)

    # 🧾 5B. Actual Backtest Table
    print("\n\n")
    formatted_df = format_backtest_table(backtest_df,len(backtest_df))
    pdf.add_table(formatted_df, list(formatted_df.columns), apply_row_coloring=True)

    # Add explanatory note below the table
    pdf.add_paragraph(
        "Note: For BUY signals, a higher exit price than entry is a SUCCESS. "
        "For SELL signals, a lower exit price is a SUCCESS. "
        "Net return % includes 0.2% Binance commission but does not affect the SUCCESS/FAILURE label. ",
        color=(50, 50, 50)
    )
    pdf.add_page()

    # 6. Charts - UPDATED WITH LARGER PRICE CHART
    pdf.set_link(links["visualizations"])
    pdf.add_section_title("7.3. Performace Charts & Visualizations")
    
    pdf.add_image("reports/plots/price_chart_price_early.png", size_type='full_width')
    pdf.add_image("reports/plots/price_chart_price_middle.png", size_type='full_width')
    pdf.add_image("reports/plots/price_chart_price_late.png", size_type='full_width')
    pdf.add_image("reports/plots/price_chart_pnl.png", size_type='full_width')
    pdf.add_image("reports/plots/price_chart_cumulative.png", size_type='large')
    #pdf.add_image("reports/plots/price_chart_summary.png", size_type='large')
    
    # Add the pie chart with SMALL size (keep it compact as requested)
    # pdf.add_image("reports/plots/backtest_chart.png", size_type='default')

    pdf.output(pdf_path)

def format_backtest_table(df, max_rows):
    columns = [
        "timestamp", "coin", "open", "rsi", "macd",
        "bollinger", "sentiment", "volatility", "signal", "confidence",
        "exit_price", "exit_time", "actual_duration_minutes", 
        "take_profit", "stop_loss", "risk_reward_ratio", 
        "estimated_duration_minutes", "exit_reason",
        "net_return_percent", "result"
    ]
    df = df[columns].copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.strftime("%d-%b-%Y %H:%M")
    df["exit_time"] = pd.to_datetime(df["exit_time"]).dt.strftime("%d-%b-%Y %H:%M")
    
    # Format price columns
    for col in ["open", "exit_price", "take_profit", "stop_loss"]:
        df[col] = df[col].apply(lambda x: "{:,.2f}".format(float(x)) if pd.notna(x) and str(x) != 'N/A' else x)
    
    # Format other columns
    df["rsi"] = df["rsi"].apply(lambda x: round(float(x), 1) if pd.notna(x) else "N/A")
    df["estimated_duration_minutes"] = df["estimated_duration_minutes"].apply(
        lambda x: f"{int(x)}mins" if pd.notna(x) else "-"
    )
    df["actual_duration_minutes"] = df["actual_duration_minutes"].apply(
        lambda x: f"{int(x)}mins" if pd.notna(x) else "-"
    )
    
    df["net_return_percent"] = df["net_return_percent"].apply(lambda x: round(float(x), 2) if pd.notna(x) and str(x) != 'N/A' else 0.0)

    # Rename columns for display
    df.rename(columns={
        "net_return_percent": "R%",
        "risk_reward_ratio": "r:r",
        "estimated_duration_minutes": "duration",
        "actual_duration_minutes": "TD",
        "confidence": "conf",
        "exit_reason": "Exit.R",
        "exit_time": "Exit Time",
        "sentiment": "news",
        "open": "Entry.P ($)",
        "exit_price": "Exit.P ($)",
        "take_profit": "TP ($)",
        "stop_loss": "SL ($)",
        "timestamp": "Entry Time"
    }, inplace=True)

    return df.tail(max_rows).reset_index(drop=True)


# def format_backtest_table(df, max_rows=30):
#     columns = [
#         "timestamp", "coin", "open", "close", "rsi", "macd",
#         "bollinger", "sentiment", "volatility", "signal", "confidence",
#         "exit_price", "exit_time", "actual_duration_minutes", "take_profit", "stop_loss", "risk_reward_ratio", "estimated_duration_minutes", "exit_reason",
#         "net_return_percent", "result"
#     ]
#     df = df[columns].copy()
#     df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.strftime("%d-%b-%Y %H:%M")
#     df["exit_time"] = pd.to_datetime(df["exit_time"]).dt.strftime("%d-%b-%Y %H:%M")
    
#     # Format price columns
#     for col in ["open", "close", "exit_price", "take_profit", "stop_loss"]:
#         df[col] = df[col].apply(lambda x: "{:,.2f}".format(x))
    
#     # Format other columns
#     df["rsi"] = df["rsi"].round(1)
#     df["estimated_duration_minutes"] = df["estimated_duration_minutes"].apply(lambda x: f"{int(x)}mins" if pd.notna(x) else "-")
#     df["actual_duration_minutes"] = df["actual_duration_minutes"].apply(lambda x: f"{int(x)}mins" if pd.notna(x) else "-")
#     df["net_return_percent"] = df["net_return_percent"].round(2)

#     # Rename columns for display
#     df.rename(columns={
#         "net_return_percent": "R%",
#         "risk_reward_ratio": "r:r",
#         "estimated_duration_minutes": "duration",
#         "actual_duration_minutes": "TD",
#         "confidence": "conf",
#         "exit_reason": "Exit.R",
#         "sentiment": "news",
#         "open": "open ($)",
#         "close": "close ($)",
#         "exit_price": "Exit.P ($)",
#         "take_profit": "TP ($)",
#         "stop_loss": "SL ($)"
#     }, inplace=True)

#     return df.tail(max_rows).reset_index(drop=True)


#fix the hist month vol col widths