# reports/visualization.py

import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from matplotlib.dates import DateFormatter
import matplotlib.ticker as mticker

def plot_price_with_indicators(df, backtest_df, symbol, save_path):
    if not isinstance(backtest_df, pd.DataFrame):
        raise ValueError(f"Expected backtest_df to be a DataFrame, but got {type(backtest_df)}")

    # Generate base filename without extension
    base_path = save_path.rsplit('.', 1)[0] if '.' in save_path else save_path
    
    # Chart 1: Price charts with entry/exit points - Split into 3 time periods
    if not backtest_df.empty and 'timestamp' in backtest_df.columns:
        backtest_df['timestamp'] = pd.to_datetime(backtest_df['timestamp'])
        df.index = pd.to_datetime(df.index)
        
        # Divide data into 3 equal time periods
        start_date = df.index.min()
        end_date = df.index.max()
        total_duration = end_date - start_date
        period_duration = total_duration / 3
        
        periods = [
            (start_date, start_date + period_duration, "Early Period", "early"),
            (start_date + period_duration, start_date + 2 * period_duration, "Middle Period", "middle"),
            (start_date + 2 * period_duration, end_date, "Late Period", "late")
        ]
        
        for period_idx, (period_start, period_end, period_name, period_suffix) in enumerate(periods):
            # Create individual figure for each period
            fig, ax = plt.subplots(1, 1, figsize=(16, 10))

            
            # Filter data for this period
            period_df = df[(df.index >= period_start) & (df.index <= period_end)]
            period_backtest = backtest_df[(backtest_df['timestamp'] >= period_start) & (backtest_df['timestamp'] <= period_end)]
            
            if period_df.empty:
                ax.text(0.5, 0.5, f'No data for {period_name}', ha='center', va='center', transform=ax.transAxes, fontsize=14)
                ax.set_title(f"{symbol.upper()} - {period_name}", fontweight='bold', fontsize=16)
                continue
            
            # Plot price data
            ax.plot(period_df.index, period_df['close'], label='Close Price', color='black', linewidth=1.5)
            avg_price = period_df['close'].mean()
            ax.axhline(avg_price, color='orange', linestyle='--', label='Average Price', alpha=0.7)
            ax.text(period_df.index[-1], avg_price * 0.998, f' ${avg_price:.2f}', 
                    verticalalignment='top', fontsize=10, color='orange', fontweight='bold')

            # Track plotted signals for legend management
            plotted_signals = {
                'buy_success': False,
                'buy_failure': False,
                'sell_success': False,
                'sell_failure': False
            }

            for i, (_, row) in enumerate(period_backtest.iterrows()):
                try:
                    entry_time = pd.to_datetime(row['timestamp'])
                    if entry_time in period_df.index:
                        entry_price = period_df.loc[entry_time, 'close']
                        signal = row.get('signal', 'HOLD')
                        
                        # Skip if not a valid signal
                        if signal not in ['BUY', 'SELL']:
                            continue
                        
                        # Use the 'result' column from backtest data instead of calculating
                        actual_success = False
                        exit_price = None
                        exit_time = None
                        
                        # Check if result column exists and use it
                        if 'result' in row and not pd.isna(row['result']):
                            actual_success = str(row['result']).upper() == 'SUCCESS'
                        
                        if 'exit_price' in row and not pd.isna(row['exit_price']):
                            try:
                                # Handle exit_price parsing more robustly
                                exit_price_str = str(row['exit_price']).replace(',', '').replace('$', '').strip()
                                exit_price = float(exit_price_str)
                                
                                # Use exit_time from data if available, otherwise estimate
                                if 'exit_time' in row and not pd.isna(row['exit_time']):
                                    exit_time = pd.to_datetime(row['exit_time'])
                                else:
                                    # Fallback to duration-based calculation if available
                                    if 'duration' in row and not pd.isna(row['duration']):
                                        duration_str = str(row['duration'])
                                        if 'mins' in duration_str:
                                            minutes = int(duration_str.replace('mins', '').strip())
                                            exit_time = entry_time + pd.Timedelta(minutes=minutes)
                                        else:
                                            exit_time = entry_time + pd.Timedelta(hours=1)
                                    else:
                                        exit_time = entry_time + pd.Timedelta(hours=1)
                                
                                # If result column wasn't available, fall back to price comparison
                                if 'result' not in row or pd.isna(row['result']):
                                    if signal == 'BUY':
                                        actual_success = exit_price > entry_price
                                    elif signal == 'SELL':
                                        actual_success = exit_price < entry_price
                                        
                            except Exception as e:
                                print(f"[Warning] Could not parse exit_price for trade {i}: {e}")
                                continue
                        
                        # Set colors and markers based on actual success/failure
                        if actual_success:
                            line_color = 'green'
                            marker_color = 'darkgreen'
                            alpha = 0.9
                        else:
                            line_color = 'red'
                            marker_color = 'darkred'
                            alpha = 0.9
                        
                        # Set marker based on signal type
                        if signal == 'BUY':
                            entry_marker = '^'  # Up arrow for buy
                            marker_size = 150
                        else:  # SELL
                            entry_marker = 'v'  # Down arrow for sell
                            marker_size = 150
                        
                        # Determine label for legend (only add if not already plotted)
                        label_key = f"{signal.lower()}_{'success' if actual_success else 'failure'}"
                        entry_label = None
                        exit_label = None
                        line_label = None
                        
                        if not plotted_signals[label_key]:
                            if signal == 'BUY':
                                entry_label = f'BUY Entry ({"Profit" if actual_success else "Loss"})'
                                exit_label = f'BUY Exit ({"Profit" if actual_success else "Loss"})'
                                line_label = f'BUY Trade ({"Profit" if actual_success else "Loss"})'
                            else:
                                entry_label = f'SELL Entry ({"Profit" if actual_success else "Loss"})'
                                exit_label = f'SELL Exit ({"Profit" if actual_success else "Loss"})'
                                line_label = f'SELL Trade ({"Profit" if actual_success else "Loss"})'
                            plotted_signals[label_key] = True

                        # Plot entry point with proper positioning
                        ax.scatter(entry_time, entry_price, marker=entry_marker, 
                                color=marker_color, s=marker_size, zorder=6, 
                                edgecolors='white', linewidth=2.5, alpha=alpha,
                                label=entry_label)

                        # Plot exit point and connecting line if exit data exists
                        if exit_price is not None and exit_time is not None:
                            # Ensure exit_time is within chart bounds
                            if exit_time <= period_df.index[-1]:
                                # Plot connecting line
                                ax.plot([entry_time, exit_time], [entry_price, exit_price], 
                                    color=line_color, linewidth=3, alpha=0.8, zorder=4,
                                    label=line_label)
                                
                                # Plot exit point (square marker)
                                ax.scatter(exit_time, exit_price, marker='s', 
                                        color=line_color, s=100, zorder=5, 
                                        alpha=0.9, edgecolors='white', linewidth=1.5,
                                        label=exit_label)
                                
                                # Calculate P&L based on signal type
                                if signal == 'BUY':
                                    pnl = exit_price - entry_price
                                elif signal == 'SELL':
                                    pnl = entry_price - exit_price
                                
                                pnl_pct = (pnl / entry_price) * 100
                                
                                # Calculate time and price ranges for positioning
                                time_range = period_df.index[-1] - period_df.index[0]
                                price_range = period_df['close'].max() - period_df['close'].min()
                                
                                # Position annotation to the side of the trade
                                mid_time = entry_time + (exit_time - entry_time) / 2
                                mid_price = (entry_price + exit_price) / 2
                                
                                # Calculate horizontal offset (to the side)
                                time_offset = time_range * 0.08  # Move annotation 8% of time range to the side
                                
                                # Alternate sides based on trade index to avoid clustering
                                if i % 2 == 0:
                                    # Even trades: place to the right
                                    annotation_time = mid_time + time_offset
                                    ha_alignment = 'left'
                                else:
                                    # Odd trades: place to the left
                                    annotation_time = mid_time - time_offset
                                    ha_alignment = 'right'
                                
                                # Add small vertical offset for better distribution
                                vertical_offset = price_range * 0.03 * (1 if i % 4 < 2 else -1)
                                annotation_y = mid_price + vertical_offset
                                
                                # Ensure annotation stays within chart bounds
                                chart_top = period_df['close'].max() + price_range * 0.05
                                chart_bottom = period_df['close'].min() - price_range * 0.05
                                annotation_y = max(chart_bottom, min(chart_top, annotation_y))
                                
                                # Ensure time annotation stays within reasonable bounds
                                chart_start = period_df.index[0] - time_range * 0.05
                                chart_end = period_df.index[-1] + time_range * 0.05
                                annotation_time = max(chart_start, min(chart_end, annotation_time))
                                
                                # Add P&L annotation with side positioning
                                ax.annotate(f'${pnl:.2f}\n({pnl_pct:+.1f}%)', 
                                        xy=(mid_time, mid_price), 
                                        xytext=(annotation_time, annotation_y),
                                        ha=ha_alignment, va='center',
                                        fontsize=8, fontweight='bold',
                                        color=line_color,
                                        bbox=dict(boxstyle='round,pad=0.4', 
                                                    facecolor='white', 
                                                    edgecolor=line_color, 
                                                    alpha=0.9,
                                                    linewidth=1.5),
                                        arrowprops=dict(arrowstyle='->', 
                                                        color=line_color, 
                                                        alpha=0.7, 
                                                        lw=1.5,
                                                        connectionstyle="arc3,rad=0.2"))

                except Exception as e:
                    print(f"[Warning] Could not plot backtest entry {i}: {e}")

            # Format x-axis to show abbreviated month names
            ax.xaxis.set_major_formatter(DateFormatter('%d %b %Y'))
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')

            ax.set_title(f"{symbol.upper()} - {period_name} Price with Entry/Exit Points & P&L Analysis", 
                        fontweight='bold', fontsize=16, pad=15)
            ax.set_ylabel("Price ($)", fontweight='bold', fontsize=12)
            ax.set_xlabel("Date", fontweight='bold', fontsize=12)
            ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'${x:,.0f}'))

            # Create a more organized legend
            legend = ax.legend(loc='upper left', bbox_to_anchor=(0, 1), fontsize=9, 
                            frameon=True, fancybox=True, shadow=True, ncol=2)
            legend.get_frame().set_facecolor('white')
            legend.get_frame().set_alpha(0.95)

            # Add grid for better readability
            ax.grid(True, alpha=0.3, linestyle='--')

            # Add a subtle background color
            ax.set_facecolor('#fafafa')

            # Improve layout and save individual chart
            plt.tight_layout()
            
            # Save each period as separate file
            period_path = f"{base_path}_price_{period_suffix}.png"
            plt.savefig(period_path, dpi=300, bbox_inches='tight', facecolor='white')
            plt.close()
            print(f"{period_name} chart saved to: {period_path}")

    else:
        # If no backtest data, just show price for all periods
        start_date = df.index.min()
        end_date = df.index.max()
        total_duration = end_date - start_date
        period_duration = total_duration / 3
        
        periods = [
            (start_date, start_date + period_duration, "Early Period", "early"),
            (start_date + period_duration, start_date + 2 * period_duration, "Middle Period", "middle"),
            (start_date + 2 * period_duration, end_date, "Late Period", "late")
        ]
        
        for period_idx, (period_start, period_end, period_name, period_suffix) in enumerate(periods):
            fig, ax = plt.subplots(1, 1, figsize=(16, 10))
            period_df = df[(df.index >= period_start) & (df.index <= period_end)]
            
            if not period_df.empty:
                ax.plot(period_df.index, period_df['close'], label='Close Price', color='black', linewidth=1.5)
                avg_price = period_df['close'].mean()
                ax.axhline(avg_price, color='orange', linestyle='--', label='Average Price', alpha=0.7)
            
            ax.set_title(f"{symbol.upper()} - {period_name}", fontweight='bold', fontsize=16)
            ax.set_ylabel("Price ($)", fontweight='bold', fontsize=12)
            ax.set_xlabel("Date", fontweight='bold', fontsize=12)
            ax.grid(True, alpha=0.3, linestyle='--')
            ax.set_facecolor('#fafafa')
            
            plt.tight_layout()
            period_path = f"{base_path}_price_{period_suffix}.png"
            plt.savefig(period_path, dpi=300, bbox_inches='tight', facecolor='white')
            plt.close()
            print(f"{period_name} chart saved to: {period_path}")

    print(f"All 3 price charts saved separately with suffixes: _early, _middle, _late")

    # Chart 2: Individual Trade P&L bars with Risk/Reward Analysis
    fig, ax = plt.subplots(1, 1, figsize=(16, 9))
    if not backtest_df.empty:
        trade_data = []
        
        for i, (_, row) in enumerate(backtest_df.iterrows()):
            # Get required values
            entry_price = row.get('open', 0)
            exit_price = row.get('exit_price', 0)
            stop_loss_price = row.get('stop_loss', None)
            take_profit_price = row.get('take_profit', None)
            signal = row.get('signal', 'HOLD')
            exit_reason = row.get('exit_reason', 'TIME')
            result = row.get('result', 'NEUTRAL')
            
            # Calculate actual P&L based on exit_price
            if entry_price and exit_price and entry_price != 0:
                if signal == "BUY":
                    pnl_percent = (((exit_price - entry_price) / entry_price) * 100)-0.2
                elif signal == "SELL":
                    pnl_percent = (((entry_price - exit_price) / entry_price) * 100)-0.2
                else:
                    pnl_percent = 0
            else:
                pnl_percent = 0
            
            # Calculate stop loss percentage
            stop_loss_pct = None
            if stop_loss_price is not None and entry_price and entry_price != 0:
                try:
                    sl_price = float(stop_loss_price)
                    entry_px = float(entry_price)
                    
                    if signal == "BUY":
                        stop_loss_pct = ((sl_price - entry_px) / entry_px) * 100
                    elif signal == "SELL":
                        stop_loss_pct = ((entry_px - sl_price) / entry_px) * 100
                except (ValueError, TypeError):
                    pass
            
            # Calculate take profit percentage
            take_profit_pct = None
            if take_profit_price is not None and entry_price and entry_price != 0:
                try:
                    tp_price = float(take_profit_price)
                    entry_px = float(entry_price)
                    
                    if signal == "BUY":
                        take_profit_pct = ((tp_price - entry_px) / entry_px) * 100
                    elif signal == "SELL":
                        take_profit_pct = ((entry_px - tp_price) / entry_px) * 100
                except (ValueError, TypeError):
                    pass
            
            trade_data.append({
                'trade_num': i+1,
                'pnl': pnl_percent,
                'result': result,
                'signal': signal,
                'stop_loss_percent': stop_loss_pct,
                'take_profit_percent': take_profit_pct,
                'exit_reason': exit_reason,
                'entry_price': entry_price,
                'exit_price': exit_price,
                'stop_loss_price': stop_loss_price,
                'take_profit_price': take_profit_price
            })
        
        if trade_data:
            trade_df = pd.DataFrame(trade_data)
            
            # Color bars based on actual P&L (GREEN for profit, RED for loss)
            colors = ['green' if pnl > 0 else 'red' if pnl < 0 else 'gray' 
                    for pnl in trade_df['pnl']]
            
            bars = ax.bar(trade_df['trade_num'], trade_df['pnl'], color=colors, alpha=0.7, edgecolor='black')
            ax.axhline(0, color='black', linestyle='-', alpha=0.5)
            
            # Track if we've added legend labels
            risk_zone_added = False
            profit_zone_added = False
            
            # Add risk and reward zones for each trade based on exit reason
            for i, (_, row) in enumerate(trade_df.iterrows()):
                trade_num = row['trade_num']
                pnl = row['pnl']
                exit_reason = row['exit_reason']
                
                # Logic based on exit reason and P&L
                if exit_reason == 'TP':
                    # Take profit hit - only show stop loss zone (what could have been lost)
                    if row['stop_loss_percent'] is not None:
                        stop_loss_pct = row['stop_loss_percent']
                        label = 'Risk Zone (Stop Loss)' if not risk_zone_added else ""
                        ax.fill_between([trade_num - 0.4, trade_num + 0.4], 
                                    stop_loss_pct, 0, alpha=0.3, color='red', 
                                    label=label)
                        risk_zone_added = True
                        
                elif exit_reason == 'SL':
                    # Stop loss hit - only show take profit zone (what could have been gained)
                    if row['take_profit_percent'] is not None:
                        take_profit_pct = row['take_profit_percent']
                        label = 'Profit Zone (Take Profit)' if not profit_zone_added else ""
                        ax.fill_between([trade_num - 0.4, trade_num + 0.4], 
                                    0, take_profit_pct, alpha=0.3, color='green',
                                    label=label)
                        profit_zone_added = True
                        
                elif exit_reason == 'TIME':
                    # Time exit - show both zones
                    # Show stop loss zone
                    if row['stop_loss_percent'] is not None:
                        stop_loss_pct = row['stop_loss_percent']
                        label = 'Risk Zone (Stop Loss)' if not risk_zone_added else ""
                        if pnl >= 0:
                            # Profitable time exit - show what could have been lost
                            ax.fill_between([trade_num - 0.4, trade_num + 0.4], 
                                        stop_loss_pct, 0, alpha=0.3, color='red', 
                                        label=label)
                        else:
                            # Losing time exit - show additional potential loss
                            ax.fill_between([trade_num - 0.4, trade_num + 0.4], 
                                        pnl, min(pnl, stop_loss_pct), alpha=0.3, color='darkred', 
                                        label=label)
                        risk_zone_added = True
                    
                    # Show take profit zone
                    if row['take_profit_percent'] is not None:
                        take_profit_pct = row['take_profit_percent']
                        label = 'Profit Zone (Take Profit)' if not profit_zone_added else ""
                        if pnl <= 0:
                            # Losing time exit - show what could have been gained
                            ax.fill_between([trade_num - 0.4, trade_num + 0.4], 
                                        0, take_profit_pct, alpha=0.3, color='green',
                                        label=label)
                        else:
                            # Profitable time exit - show additional potential gain
                            ax.fill_between([trade_num - 0.4, trade_num + 0.4], 
                                        pnl, max(pnl, take_profit_pct), alpha=0.3, color='darkgreen',
                                        label=label)
                        profit_zone_added = True
            
            # Add value labels on bars
            for bar, pnl, exit_reason in zip(bars, trade_df['pnl'], trade_df['exit_reason']):
                height = bar.get_height()
                # Add exit reason indicator
                exit_indicator = {'TP': ' (TP)', 'SL': ' (SL)', 'TIME': ' (T)'}.get(exit_reason, '')
                ax.text(bar.get_x() + bar.get_width()/2., height + (0.08 if height >= 0 else -0.08),
                        f'{pnl:.1f}%{exit_indicator}', ha='center', va='bottom' if height >= 0 else 'top', 
                        fontsize=8, fontweight='bold')
            
            # Debug: Print trade data to see what's available
            print("\nCorrected Trade data summary:")
            print(f"{'Trade':<5} {'PnL':<8} {'Signal':<4} {'Entry':<8} {'Exit':<8} {'SL%':<8} {'TP%':<8} {'Exit':<4}")
            print("-" * 70)
            for i, row in trade_df.iterrows():
                sl_pct = f"{row['stop_loss_percent']:.1f}%" if row['stop_loss_percent'] is not None else "None"
                tp_pct = f"{row['take_profit_percent']:.1f}%" if row['take_profit_percent'] is not None else "None"
                print(f"{row['trade_num']:<5} {row['pnl']:<8.1f} {row['signal']:<4} {row['entry_price']:<8.2f} {row['exit_price']:<8.2f} {sl_pct:<8} {tp_pct:<8} {row['exit_reason']:<4}")

    ax.set_title(f"{symbol.upper()} - Individual Trade P&L with Risk/Reward Analysis", fontweight='bold', fontsize=16)
    ax.set_xlabel("Trade Number")
    ax.set_ylabel("Return %")
    ax.grid(True, alpha=0.3)

    # Set axis limits to ensure all content fits
    ax.set_xlim(0.5, len(trade_df) + 0.5)
    # Add some padding to y-axis based on data range
    y_min = min(trade_df['pnl'].min(), min([t['stop_loss_percent'] for t in trade_data if t['stop_loss_percent'] is not None], default=0))
    y_max = max(trade_df['pnl'].max(), max([t['take_profit_percent'] for t in trade_data if t['take_profit_percent'] is not None], default=0))
    y_padding = (y_max - y_min) * 0.15
    ax.set_ylim(y_min - y_padding, y_max + y_padding)

    # Add legend with better positioning
    handles, labels = ax.get_legend_handles_labels()
    if handles:
        ax.legend(handles, labels, loc='upper left', fontsize=10, framealpha=0.9)

    # Add summary statistics based on actual P&L
    if trade_data:
        successful_trades = [t for t in trade_data if t['pnl'] > 0]
        failed_trades = [t for t in trade_data if t['pnl'] < 0]
        
        win_rate = len(successful_trades) / len(trade_data) * 100 if trade_data else 0
        avg_win = np.mean([t['pnl'] for t in successful_trades]) if successful_trades else 0
        avg_loss = np.mean([t['pnl'] for t in failed_trades]) if failed_trades else 0
        
        stats_text = f"Win Rate: {win_rate:.1f}% | Avg Win: {avg_win:.1f}% | Avg Loss: {avg_loss:.1f}%"
        ax.text(0.02, 0.02, stats_text, transform=ax.transAxes, fontsize=10, 
                verticalalignment='bottom', bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.9))

    plt.tight_layout()
    pnl_path = f"{base_path}_pnl.png"
    plt.savefig(pnl_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"P&L chart saved to: {pnl_path}")

    # Chart 3: Cumulative returns (FIXED)
    fig, ax = plt.subplots(1, 1, figsize=(14, 8))
    if not backtest_df.empty and 'net_return_percent' in backtest_df.columns:
        # FIXED: Use compound returns (same as evaluator.py)
        return_multipliers = 1 + (backtest_df['net_return_percent'] / 100)
        cumulative_multipliers = return_multipliers.cumprod()
        cumulative_returns = (cumulative_multipliers - 1) * 100  # Convert back to percentage
        
        ax.fill_between(range(1, len(cumulative_returns) + 1), cumulative_returns, 
                        alpha=0.6, color='lightblue', label='Cumulative Returns')
        ax.plot(range(1, len(cumulative_returns) + 1), cumulative_returns, color='blue', linewidth=2)
        
        # Add markers for each trade
        ax.scatter(range(1, len(cumulative_returns) + 1), cumulative_returns, 
                color='red', s=30, zorder=5)
        
        # Add trade numbers as text labels
        for i, (trade_num, cum_return) in enumerate(zip(range(1, len(cumulative_returns) + 1), cumulative_returns)):
            ax.annotate(str(trade_num), (trade_num, cum_return), 
                    textcoords="offset points", xytext=(0,10), ha='center', 
                    fontsize=8, color='darkred', fontweight='bold')
        
        ax.axhline(0, color='black', linestyle='-', alpha=0.3)
        
        # Add final cumulative return value
        final_return = cumulative_returns.iloc[-1] if len(cumulative_returns) > 0 else 0
        ax.text(len(cumulative_returns), final_return, f' {final_return:.1f}%', 
                fontsize=12, fontweight='bold', color='blue')

    ax.set_title(f"{symbol.upper()} - Cumulative Returns (Binance 0.2% commission included)", fontweight='bold', fontsize=16)
    ax.set_xlabel("Trade Sequence")
    ax.set_ylabel("Cumulative Return %")
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    cumulative_path = f"{base_path}_cumulative.png"
    plt.savefig(cumulative_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Cumulative returns chart saved to: {cumulative_path}")

    # Optional: Print verification that both methods now match
    if not backtest_df.empty and 'net_return_percent' in backtest_df.columns:
        # Method from evaluator.py
        df_temp = backtest_df.copy()
        df_temp["return_multiplier"] = 1 + (df_temp["net_return_percent"] / 100)
        evaluator_result = round((df_temp["return_multiplier"].prod() - 1) * 100, 2)
        
        # Method from chart
        chart_result = round(final_return, 2)
        
        print(f"🔍 Verification - Evaluator result: {evaluator_result}%, Chart result: {chart_result}%")
        print(f"Methods match: {evaluator_result == chart_result}")

    # Chart 4: Trade summary statistics
    fig, ax = plt.subplots(1, 1, figsize=(10, 8))
    if not backtest_df.empty and 'result' in backtest_df.columns:
        summary = backtest_df['result'].value_counts()
        colors = ['green' if label == 'SUCCESS' else 'red' if label == 'FAILURE' else 'gray' 
                for label in summary.index]
        
        wedges, texts, autotexts = ax.pie(summary, labels=summary.index, colors=colors, 
                                        autopct='%1.1f%%', startangle=140)
        
        # Add count annotations
        for i, (label, count) in enumerate(summary.items()):
            texts[i].set_text(f'{label}\n({count} trades)')
            texts[i].set_fontsize(12)
            autotexts[i].set_fontweight('bold')
            autotexts[i].set_fontsize(11)

    ax.set_title(f"{symbol.upper()} - Trade Results Distribution", fontweight='bold', fontsize=16)

    plt.tight_layout()
    summary_path = f"{base_path}_summary.png"
    plt.savefig(summary_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Summary chart saved to: {summary_path}")

    print(f"All 4 charts saved as separate files with prefix: {base_path}")

def plot_backtest_results(df, save_path):
    if not isinstance(df, pd.DataFrame):
        raise ValueError(f"Expected DataFrame for backtest results, got {type(df)}")

    if df.empty or 'result' not in df.columns:
        print("No backtest data available for plotting.")
        return

    summary = df['result'].value_counts()
    colors = ['green' if label == 'SUCCESS' else 'red' if label == 'FAILURE' else 'gray' for label in summary.index]

    plt.figure(figsize=(8, 8))
    plt.pie(
        summary,
        labels=[f'{label}\n({count} trades)' for label, count in summary.items()],
        colors=colors,
        autopct='%1.1f%%',
        startangle=140,
        textprops={'fontsize': 14}  # makes % and labels bigger
    )
    plt.title("Backtest Result Distribution", fontsize=16, fontweight="bold")  # 🔥 bigger title
    plt.tight_layout()
    plt.savefig(save_path, dpi=300)
    plt.close()

    print(f"Backtest pie chart saved to: {save_path}")