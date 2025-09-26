from typing import Dict, List, Any
from colorama import Fore, Style, init
import json
from prettytable import PrettyTable

init(autoreset=True)

class VerificationTableViewer:
    def __init__(self):
        self.verdict_colors = {
            "SUPPORTED": Fore.GREEN + "Pass" + Style.RESET_ALL,
            "CONTRADICTED": Fore.RED + "Fail" + Style.RESET_ALL,
            "PARTIAL": Fore.YELLOW + "Partial" + Style.RESET_ALL,
            "NOT_FOUND": Fore.BLUE + "Not Found" + Style.RESET_ALL
        }


    def format_status(self, verdict: str) -> str:
        """Format verdict as colored status"""
        return self.verdict_colors.get(verdict, verdict)

    def get_display_length(self, text: str) -> int:
        """Get the actual display length of text (excluding ANSI color codes)"""
        import re
        # Remove ANSI escape sequences
        ansi_escape = re.compile(r'\x1b\[[0-9;]*m')
        clean_text = ansi_escape.sub('', text)
        return len(clean_text)


    def truncate_text(self, text: str, max_length: int = 40) -> str:
        """Truncate text to fit in table columns"""
        if len(text) <= max_length:
            return text
        return text[:max_length-3] + "..."

    def extract_citations_summary(self, citations: List[Dict]) -> str:
        """Extract summary of citations for dependencies column"""
        if not citations:
            return "-"

        summaries = []
        for citation in citations[:2]:  # Show max 2 citations
            doc_id = citation.get("docId", "").replace(".txt", "")
            version = citation.get("version", "")
            page = citation.get("page", "")

            if doc_id and page:
                if "rfp" in doc_id.lower():
                    summaries.append(f"RFP v{version} p{page}")
                elif "internal" in doc_id.lower() or "spec" in doc_id.lower():
                    summaries.append(f"Internal Spec v{version}, p{page}")
                else:
                    summaries.append(f"{doc_id} v{version} p{page}")

        result = ", ".join(summaries)
        if len(citations) > 2:
            result += f" (+{len(citations)-2} more)"

        return result if result else "-"


    def display_verification_table(self, result_data: Dict[str, Any]):
        """Display verification results as a formatted table using PrettyTable"""
        print(f"\n{Fore.GREEN}{'='*100}")
        print(f"VERIFICATION RESULTS TABLE")
        print(f"Document: {result_data.get('title', 'Unknown')}")
        print(f"Session: {result_data.get('document_id', 'Unknown')}")
        print(f"{'='*100}{Style.RESET_ALL}")

        # Create main table
        table = PrettyTable()
        table.field_names = ["ID", "Block/Claim", "Status", "Confidence", "Dependencies"]
        table.align["Block/Claim"] = "l"
        table.align["Dependencies"] = "l"
        table.max_width["Block/Claim"] = 45
        table.max_width["Dependencies"] = 30

        blocks = result_data.get('blocks', [])

        for i, block in enumerate(blocks):
            block_id = block.get('block_id', '').upper()
            block_title = block.get('title', 'Unknown Block').replace("Block: ", "")

            # Add block header row
            table.add_row([
                f"{Fore.CYAN}{block_id}{Style.RESET_ALL}",
                f"{Fore.CYAN}{self.truncate_text(block_title, 45)}{Style.RESET_ALL}",
                f"{Fore.CYAN}-{Style.RESET_ALL}",
                f"{Fore.CYAN}-{Style.RESET_ALL}",
                f"{Fore.CYAN}-{Style.RESET_ALL}"
            ])

            # Add claims under this block
            claims = block.get('claims', [])
            for claim in claims:
                claim_id = claim.get('claim_id', '').replace('claim-', '').replace('-', '.')
                claim_title = claim.get('title', 'Unknown Claim').replace("Claim: ", "")
                if claim_title.endswith("..."):
                    claim_title = claim_title[:-3]

                claim_details = claim.get('details', {})
                verdict = claim_details.get('verdict', 'NOT_FOUND')
                confidence = claim_details.get('confidence', 0)
                citations = claim_details.get('citations', [])

                formatted_status = self.format_status(verdict)
                dependencies = self.extract_citations_summary(citations)

                table.add_row([
                    f"  {claim_id}",
                    f"└─ {self.truncate_text(claim_title, 40)}",
                    formatted_status,
                    f"{confidence}%",
                    self.truncate_text(dependencies, 28)
                ])

            # Add separator between blocks (except after last block)
            if i < len(blocks) - 1:
                table.add_row(["-" * 8, "-" * 45, "-" * 12, "-" * 8, "-" * 30])

        print(table)

        # Print summary statistics
        self.print_summary_stats(result_data)

    def print_summary_stats(self, result_data: Dict[str, Any]):
        """Print summary statistics using PrettyTable"""
        # Count verdicts
        verdict_counts = {"SUPPORTED": 0, "CONTRADICTED": 0, "PARTIAL": 0, "NOT_FOUND": 0}
        total_claims = 0

        for block in result_data.get('blocks', []):
            for claim in block.get('claims', []):
                verdict = claim.get('details', {}).get('verdict', 'NOT_FOUND')
                verdict_counts[verdict] = verdict_counts.get(verdict, 0) + 1
                total_claims += 1

        # Create summary table
        print(f"\n{Fore.CYAN}SUMMARY STATISTICS:{Style.RESET_ALL}")
        summary_table = PrettyTable()
        summary_table.field_names = ["Metric", "Value"]
        summary_table.align["Metric"] = "l"
        summary_table.align["Value"] = "r"

        summary_table.add_row(["Total Claims", str(total_claims)])
        summary_table.add_row([f"{Fore.GREEN}Pass (Supported){Style.RESET_ALL}", str(verdict_counts['SUPPORTED'])])
        summary_table.add_row([f"{Fore.RED}Fail (Contradicted){Style.RESET_ALL}", str(verdict_counts['CONTRADICTED'])])
        summary_table.add_row([f"{Fore.YELLOW}Partial{Style.RESET_ALL}", str(verdict_counts['PARTIAL'])])
        summary_table.add_row([f"{Fore.BLUE}Not Found{Style.RESET_ALL}", str(verdict_counts['NOT_FOUND'])])

        # Calculate pass rate
        pass_rate = ((verdict_counts['SUPPORTED'] + verdict_counts['PARTIAL']) / max(total_claims, 1)) * 100
        summary_table.add_row(["Overall Pass Rate", f"{pass_rate:.1f}%"])

        print(summary_table)

        # Performance info if available
        performance = result_data.get('performance', {})
        if performance:
            print(f"\n{Fore.CYAN}PERFORMANCE METRICS:{Style.RESET_ALL}")
            perf_table = PrettyTable()
            perf_table.field_names = ["Metric", "Value"]
            perf_table.align["Metric"] = "l"
            perf_table.align["Value"] = "r"

            perf_table.add_row(["Total Time", f"{performance.get('total_time_seconds', 0):.2f} seconds"])
            perf_table.add_row(["Avg Time/Claim", f"{performance.get('avg_time_per_claim', 0):.2f} seconds"])

            caching_status = "ENABLED" if performance.get('caching_enabled', False) else "DISABLED"
            cache_color = Fore.GREEN if performance.get('caching_enabled', False) else Fore.RED
            perf_table.add_row(["Caching", f"{cache_color}{caching_status}{Style.RESET_ALL}"])

            print(perf_table)

def load_and_display_results(json_file_path: str):
    """Load JSON file and display as table"""
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            result_data = json.load(f)

        viewer = VerificationTableViewer()
        viewer.display_verification_table(result_data)

    except FileNotFoundError:
        print(f"{Fore.RED}Error: File '{json_file_path}' not found{Style.RESET_ALL}")
    except json.JSONDecodeError as e:
        print(f"{Fore.RED}Error: Invalid JSON format - {e}{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}Error: {e}{Style.RESET_ALL}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        load_and_display_results(sys.argv[1])
    else:
        print("Usage: python table_viewer.py <json_file_path>")