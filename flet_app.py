#!c:/Users/LMiguelGJ/Desktop/LotePy/.venv/Scripts/python.exe
import flet as ft
import subprocess
import json
import os
import threading
import time
from datetime import datetime
import sys

def main(page: ft.Page):
    page.title = "LOTeka Analyzer"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 0
    page.scroll = ft.ScrollMode.AUTO
    page.adaptive = True
    
    # Custom color scheme
    page.theme = ft.Theme(
        color_scheme_seed="#6366f1",
        use_material3=True,
    )
    page.bgcolor = "#0f0f0f"
    
    # Output control for displaying script results
    output_text = ft.TextField(
        multiline=True,
        read_only=True,
        expand=True,
        max_lines=None,
        text_style=ft.TextStyle(font_family="Consolas", size=13),
        border_color="#3b3b3b",
        bgcolor="#1a1a1a",
        color="#a3e635",
        border_radius=12,
        focused_border_color="#6366f1",
        content_padding=15,
    )
    
    # Status indicators
    status_dot = ft.Container(
        width=12,
        height=12,
        bgcolor="#22c55e",
        border_radius=6,
    )
    
    status_text = ft.Text(
        "Ready",
        color="white",
        size=14,
        weight=ft.FontWeight.W_500,
    )
    
    status_indicator = ft.Container(
        content=ft.Row([
            status_dot,
            status_text,
        ], spacing=8, tight=True),
        padding=ft.padding.symmetric(horizontal=16, vertical=10),
        bgcolor="#1f1f1f",
        border_radius=20,
        border=ft.border.all(1, "#3b3b3b"),
    )
    
    # Progress bar
    progress_bar = ft.ProgressBar(
        width=300,
        visible=False,
        color="#6366f1",
        bgcolor="#2d2d2d",
        border_radius=5,
    )
    
    
    def update_status(message, color="#22c55e"):
        # Color mapping for better visual feedback
        dot_colors = {
            "#22c55e": "#22c55e",  # green
            "orange": "#f97316",
            "red": "#ef4444",
            "green": "#22c55e",
        }
        status_dot.bgcolor = dot_colors.get(color, color)
        status_text.value = message
        page.update()
    
    def append_output(text, color="#00ff00"):
        current_time = datetime.now().strftime("%H:%M:%S")
        output_text.value += f"[{current_time}] {text}\n"
        page.update()
    
    
    def run_script(script_name, description):
        def run():
            try:
                update_status(f"Running {description}...", "orange")
                progress_bar.visible = True
                page.update()
                
                append_output(f"🚀 Starting {description}...", "#ffff00")
                
                # Run the script
                process = subprocess.Popen(
                    [sys.executable, script_name],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                    universal_newlines=True
                )
                
                # Read output in real-time
                while True:
                    output = process.stdout.readline()
                    if output == '' and process.poll() is not None:
                        break
                    if output:
                        append_output(output.strip())
                
                # Check for errors
                stderr = process.stderr.read()
                if stderr:
                    append_output(f"❌ Errors:\n{stderr}", "#ff4444")
                
                return_code = process.poll()
                
                if return_code == 0:
                    update_status(f"{description} completed successfully!", "green")
                    append_output(f"✅ {description} completed successfully!", "#00ff00")
                else:
                    update_status(f"{description} failed!", "red")
                    append_output(f"❌ {description} failed with return code {return_code}", "#ff4444")
                
            except Exception as e:
                update_status(f"Error running {description}", "red")
                append_output(f"❌ Exception: {str(e)}", "#ff4444")
            finally:
                progress_bar.visible = False
                page.update()
        
        # Run in separate thread to avoid blocking UI
        thread = threading.Thread(target=run)
        thread.start()
    
    def clear_output(e):
        output_text.value = ""
        page.update()
    
    def export_results(e):
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"loteka_analysis_{timestamp}.txt"
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(output_text.value)
            
            append_output(f"📄 Results exported to {filename}", "#00ffff")
            update_status("Results exported successfully!", "green")
        except Exception as e:
            append_output(f"❌ Export failed: {str(e)}", "#ff4444")
    
    # Removed header section
    
    # Horizontal buttons - Responsive layout
    control_buttons = ft.ResponsiveRow([
        ft.Container(
            content=ft.ElevatedButton(
                content=ft.Row([
                    ft.Icon(ft.icons.CLOUD_DOWNLOAD_ROUNDED, color="white", size=18),
                    ft.Text("Update Database", color="white", weight=ft.FontWeight.W_600, size=14),
                ], spacing=8, alignment=ft.MainAxisAlignment.CENTER),
                style=ft.ButtonStyle(
                    bgcolor={ft.ControlState.DEFAULT: "#3b82f6", ft.ControlState.HOVERED: "#2563eb"},
                    padding=ft.padding.symmetric(horizontal=16, vertical=16),
                    shape=ft.RoundedRectangleBorder(radius=12),
                ),
                on_click=lambda e: run_script('scrapy.py', "Database Update"),
                tooltip="Scrape latest lottery numbers",
            ),
            col={"xs": 12, "sm": 6, "md": 3},
        ),
        ft.Container(
            content=ft.ElevatedButton(
                content=ft.Row([
                    ft.Icon(ft.icons.ANALYTICS_ROUNDED, color="white", size=18),
                    ft.Text("Run Analysis", color="white", weight=ft.FontWeight.W_600, size=14),
                ], spacing=8, alignment=ft.MainAxisAlignment.CENTER),
                style=ft.ButtonStyle(
                    bgcolor={ft.ControlState.DEFAULT: "#8b5cf6", ft.ControlState.HOVERED: "#7c3aed"},
                    padding=ft.padding.symmetric(horizontal=16, vertical=16),
                    shape=ft.RoundedRectangleBorder(radius=12),
                ),
                on_click=lambda e: run_script('main_runner.py', "Markov Analysis"),
                tooltip="Run Markov chain analysis",
            ),
            col={"xs": 12, "sm": 6, "md": 3},
        ),
        ft.Container(
            content=ft.ElevatedButton(
                content=ft.Row([
                    ft.Icon(ft.icons.CLEANING_SERVICES_ROUNDED, color="white", size=18),
                    ft.Text("Clear Output", color="white", weight=ft.FontWeight.W_600, size=14),
                ], spacing=8, alignment=ft.MainAxisAlignment.CENTER),
                style=ft.ButtonStyle(
                    bgcolor={ft.ControlState.DEFAULT: "#64748b", ft.ControlState.HOVERED: "#475569"},
                    padding=ft.padding.symmetric(horizontal=16, vertical=16),
                    shape=ft.RoundedRectangleBorder(radius=12),
                ),
                on_click=clear_output,
                tooltip="Clear console",
            ),
            col={"xs": 12, "sm": 6, "md": 3},
        ),
        ft.Container(
            content=ft.ElevatedButton(
                content=ft.Row([
                    ft.Icon(ft.icons.FILE_DOWNLOAD_ROUNDED, color="white", size=18),
                    ft.Text("Export Results", color="white", weight=ft.FontWeight.W_600, size=14),
                ], spacing=8, alignment=ft.MainAxisAlignment.CENTER),
                style=ft.ButtonStyle(
                    bgcolor={ft.ControlState.DEFAULT: "#10b981", ft.ControlState.HOVERED: "#059669"},
                    padding=ft.padding.symmetric(horizontal=16, vertical=16),
                    shape=ft.RoundedRectangleBorder(radius=12),
                ),
                on_click=export_results,
                tooltip="Export to file",
            ),
            col={"xs": 12, "sm": 6, "md": 3},
        ),
    ], spacing=10)
    
    # Top section - Buttons + Status
    top_section = ft.Container(
        content=ft.Column([
            # Status indicator
            status_indicator,
            ft.Divider(height=1, color="#3b3b3b"),
            # Buttons
            control_buttons,
            progress_bar,
        ], spacing=12, tight=True),
        padding=15,
        bgcolor="#1a1a1a",
        border_radius=12,
        border=ft.border.all(1, "#2d2d2d"),
    )
    
    # Output section - Expandable logs
    output_section = ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Icon(ft.icons.TERMINAL_ROUNDED, color="#6366f1", size=20),
                ft.Text("Logs", size=16, weight=ft.FontWeight.BOLD, color="white"),
            ], spacing=8),
            ft.Divider(height=1, color="#3b3b3b"),
            output_text,
        ], spacing=12, expand=True),
        padding=15,
        bgcolor="#1a1a1a",
        border_radius=12,
        border=ft.border.all(1, "#2d2d2d"),
        expand=True,
    )
    
    # Main layout - Buttons on top, logs at bottom
    main_content = ft.Column([
        top_section,
        output_section,
    ], spacing=15, scroll=ft.ScrollMode.AUTO)
    
    # Add everything to page
    page.add(
        ft.Container(
            content=main_content,
            padding=ft.padding.all(15),
            expand=True,
        )
    )
    
    # Welcome message - Mobile optimized
    append_output("🎯 LOTeka Analyzer v2.0", "#6366f1")
    append_output("━" * 30, "#3b3b3b")
    append_output("")
    append_output("✨ Lottery Prediction System", "#a3e635")
    append_output("📊 Markov Chain Analysis", "#94a3b8")
    append_output("")
    append_output("💡 Quick Start:", "#fbbf24")
    append_output("1. Update Database", "#94a3b8")
    append_output("2. Run Analysis", "#94a3b8")
    append_output("3. Export Results", "#94a3b8")
    append_output("")
    append_output("━" * 30, "#3b3b3b")

if __name__ == "__main__":
    # Run as mobile-optimized web application
    ft.app(
        target=main,
        port=8550,
        view=ft.AppView.WEB_BROWSER,
        assets_dir="assets",
    )
