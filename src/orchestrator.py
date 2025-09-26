import boto3
from strands import Agent
from strands.models import BedrockModel
from src.config import Config
from src.utils import load_prompt, render_prompt, load_txt_file, save_json_result
from src.agents.claim_extractor import create_claim_extractor_tool
from src.agents.evidence_retriever import create_evidence_retriever_tool
from src.agents.decision_judge import create_decision_judge_tool
from src.agents.citation_builder import create_citation_builder_tool
from src.models import VerificationResult
from pathlib import Path
import json
import uuid
from datetime import datetime
from typing import Dict, List, Any
from colorama import Fore, Style, init
import time
import shutil

# Initialize colorama
init(autoreset=True)

class DocumentVerificationOrchestrator:
    def __init__(self, config: Config):
        self.config = config
        self.model = self._create_model()
        self.prompts = load_prompt("orchestrator")

        # Create specialized agent tools
        self.claim_extractor = create_claim_extractor_tool(config)
        self.evidence_retriever = create_evidence_retriever_tool(config)
        self.decision_judge = create_decision_judge_tool(config)
        self.citation_builder = create_citation_builder_tool(config)

    def _create_model(self) -> BedrockModel:
        session = boto3.Session(
            region_name=self.config.aws_region,
            profile_name=self.config.aws_profile
        )

        return BedrockModel(
            model_id=self.config.model_id,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            boto_session=session,
        )

    def _get_terminal_width(self):
        """Get terminal width for proper formatting"""
        return shutil.get_terminal_size().columns

    def _print_box(self, title: str, content: list = None, color: str = Fore.CYAN, width: int = None):
        """Print a fancy box with title and content"""
        if width is None:
            width = min(80, self._get_terminal_width() - 4)

        # Box characters
        top_left, top_right = "┌", "┐"
        bottom_left, bottom_right = "└", "┘"
        horizontal, vertical = "─", "│"

        # Title line
        title_line = f" {title} "
        title_padding = width - len(title_line) - 2
        title_left_pad = title_padding // 2
        title_right_pad = title_padding - title_left_pad

        print(f"{color}{top_left}{horizontal * title_left_pad}{title_line}{horizontal * title_right_pad}{top_right}{Style.RESET_ALL}")

        # Content lines
        if content:
            for line in content:
                line_padding = width - len(line) - 2
                print(f"{color}{vertical}{Style.RESET_ALL} {line}{' ' * line_padding} {color}{vertical}{Style.RESET_ALL}")

        # Bottom line
        print(f"{color}{bottom_left}{horizontal * width}{bottom_right}{Style.RESET_ALL}")

    def _print_progress_bar(self, current: int, total: int, title: str = "", width: int = 40):
        """Print a progress bar"""
        if total == 0:
            return

        percentage = current / total
        filled_width = int(width * percentage)
        bar = "█" * filled_width + "░" * (width - filled_width)

        print(f"{Fore.CYAN}│{Style.RESET_ALL} {title}")
        print(f"{Fore.CYAN}│{Style.RESET_ALL} [{Fore.GREEN}{bar}{Style.RESET_ALL}] {current}/{total} ({percentage*100:.1f}%)")

    def _print_claim_header(self, claim_id: str, claim_text: str, current: int, total: int):
        """Print a fancy header for each claim"""
        width = min(80, self._get_terminal_width() - 4)

        # Truncate claim text if too long
        max_text_length = width - 20
        display_text = claim_text[:max_text_length] + "..." if len(claim_text) > max_text_length else claim_text

        print(f"\n{Fore.MAGENTA}╔{'═' * width}╗{Style.RESET_ALL}")
        print(f"{Fore.MAGENTA}║{Style.RESET_ALL} {Fore.YELLOW}CLAIM {current}/{total}: {claim_id}{Style.RESET_ALL}{' ' * (width - len(f'CLAIM {current}/{total}: {claim_id}') - 1)} {Fore.MAGENTA}║{Style.RESET_ALL}")
        print(f"{Fore.MAGENTA}║{Style.RESET_ALL} {display_text}{' ' * (width - len(display_text) - 1)} {Fore.MAGENTA}║{Style.RESET_ALL}")
        print(f"{Fore.MAGENTA}╚{'═' * width}╝{Style.RESET_ALL}")

    def _print_step_result(self, step_name: str, result: str, status: str = "SUCCESS"):
        """Print step result with status"""
        colors = {
            "SUCCESS": Fore.GREEN,
            "ERROR": Fore.RED,
            "WARNING": Fore.YELLOW,
            "PROCESSING": Fore.BLUE
        }

        color = colors.get(status, Fore.WHITE)
        print(f"  {color}[{status}] {step_name}: {result}{Style.RESET_ALL}")

    def _log_step(self, step: str, status: str = "INFO"):
        """Log a step with colored output"""
        colors = {
            "INFO": Fore.CYAN,
            "SUCCESS": Fore.GREEN,
            "WARNING": Fore.YELLOW,
            "ERROR": Fore.RED,
            "PROCESSING": Fore.BLUE
        }
        color = colors.get(status, Fore.WHITE)
        print(f"{color}[{status}]{Style.RESET_ALL} {step}")

    def load_source_documents(self) -> Dict[str, str]:
        """Load all TXT files from source directory"""
        self._log_step("Loading source documents...", "INFO")
        source_path = Path(self.config.source_dir)
        documents = {}

        for txt_file in source_path.glob("*.txt"):
            self._log_step(f"  Reading {txt_file.name}", "PROCESSING")
            doc_content = load_txt_file(str(txt_file))
            documents[txt_file.name] = doc_content

        self._log_step(f"Loaded {len(documents)} source documents", "SUCCESS")
        return documents

    def load_target_document(self) -> tuple[str, str]:
        """Load target document (first TXT file found)"""
        self._log_step("Loading target document...", "INFO")
        target_path = Path(self.config.target_dir)
        txt_files = list(target_path.glob("*.txt"))

        if not txt_files:
            raise FileNotFoundError("No TXT files found in target directory")

        target_file = txt_files[0]
        self._log_step(f"  Reading {target_file.name}", "PROCESSING")
        content = load_txt_file(str(target_file))
        self._log_step("Target document loaded", "SUCCESS")

        return target_file.name, content

    def verify_document(self, session_id: str = None) -> str:
        """
        Main verification workflow that coordinates all specialized agents
        """
        if not session_id:
            session_id = f"sess-{datetime.now().strftime('%Y-%m-%d')}-{str(uuid.uuid4())[:8]}"

        # Print welcome banner
        self._print_box(
            "DOCUMENT VERIFICATION SYSTEM",
            [
                f"Session ID: {session_id}",
                f"Model: {self.config.model_id}",
                f"Caching: {'ENABLED' if self.config.enable_caching else 'DISABLED'}",
                "",
                "Multi-Agent Analysis Pipeline Ready..."
            ],
            Fore.CYAN
        )

        # Start timing
        start_time = time.time()

        try:
            # Load documents
            print(f"\n{Fore.YELLOW}LOADING DOCUMENTS{Style.RESET_ALL}")
            target_file, target_content = self.load_target_document()
            source_documents = self.load_source_documents()

            # Create orchestrator agent with all specialized tools
            print(f"\n{Fore.BLUE}INITIALIZING AGENTS{Style.RESET_ALL}")
            self._log_step("Setting up multi-agent pipeline...", "PROCESSING")
            orchestrator = Agent(
                model=self.model,
                system_prompt=self.prompts["system_prompt"],
                tools=[
                    self.claim_extractor,
                    self.evidence_retriever,
                    self.decision_judge,
                    self.citation_builder
                ],
                trace_attributes={
                    "session.id": session_id,
                    "agent.type": "orchestrator",
                    "target.document": target_file,
                    "source.count": len(source_documents)
                }
            )

            # Prepare source documents text
            self._log_step("Preparing source documents for analysis...", "PROCESSING")
            source_docs_text = "\n\n--- DOCUMENT SEPARATOR ---\n\n".join([
                f"=== {filename} ===\n{content}"
                for filename, content in source_documents.items()
            ])

            # Create user prompt
            self._log_step("Creating analysis prompt...", "PROCESSING")
            user_prompt = render_prompt(
                self.prompts["user_prompt"],
                {
                    "target_file": target_file,
                    "target_content": target_content,
                    "source_documents": source_docs_text,
                    "session_id": session_id,
                    "timestamp": datetime.now().isoformat()
                }
            )

            # Execute verification using step-by-step multi-agent workflow
            print(f"\n{Fore.GREEN}STARTING VERIFICATION WORKFLOW{Style.RESET_ALL}")

            # Step 1: Extract claims
            self._print_box(
                "STEP 1: CLAIM EXTRACTION",
                ["Analyzing target document for verifiable claims..."],
                Fore.GREEN
            )

            claims_result = self.claim_extractor(target_file, target_content)
            claims_data = json.loads(claims_result)
            claim_count = len(claims_data.get('claims', []))

            self._print_step_result("Claims Extracted", f"{claim_count} claims found", "SUCCESS")

            # Step 2: Process each claim
            verified_claims = []
            total_claims = claim_count

            if total_claims > 0:
                print(f"\n{Fore.MAGENTA}PROCESSING CLAIMS{Style.RESET_ALL}")
                self._print_progress_bar(0, total_claims, "Overall Progress")

            for i, claim in enumerate(claims_data.get('claims', [])):
                claim_text = claim.get('claim_text', '')
                claim_id = claim.get('claim_id', f'claim-{i+1}')

                # Print fancy claim header
                self._print_claim_header(claim_id, claim_text, i+1, total_claims)

                # Get evidence for this claim
                print(f"\n  {Fore.BLUE}Evidence Retrieval{Style.RESET_ALL}")
                evidence_result = self.evidence_retriever(claim_text, source_docs_text)
                evidence_data = json.loads(evidence_result)
                evidence_count = len(evidence_data.get('evidence', []))
                self._print_step_result("Evidence Search", f"{evidence_count} pieces found", "SUCCESS")

                # Judge the claim
                print(f"\n  {Fore.MAGENTA}Decision Analysis{Style.RESET_ALL}")
                judgment_result = self.decision_judge(claim_text, evidence_result)
                judgment_data = json.loads(judgment_result)
                interim_verdict = judgment_data.get("verdict", "NOT_FOUND")
                interim_confidence = judgment_data.get("confidence", 0)

                verdict_color = {
                    "SUPPORTED": Fore.GREEN,
                    "CONTRADICTED": Fore.RED,
                    "PARTIAL": Fore.YELLOW,
                    "NOT_FOUND": Fore.BLUE
                }.get(interim_verdict, Fore.WHITE)

                self._print_step_result("Verdict", f"{verdict_color}{interim_verdict}{Style.RESET_ALL}", "SUCCESS")
                self._print_step_result("Confidence", f"{interim_confidence}%", "SUCCESS")

                # Build citations
                print(f"\n  {Fore.CYAN}Citation Generation{Style.RESET_ALL}")
                citation_result = self.citation_builder(evidence_result, json.dumps({
                    "source_files": list(source_documents.keys())
                }))
                citation_data = json.loads(citation_result)
                citation_count = len(citation_data.get('citations', []))
                self._print_step_result("Citations", f"{citation_count} generated", "SUCCESS")

                # Extract verdict with fallback
                verdict = judgment_data.get("verdict", "NOT_FOUND")
                confidence_raw = judgment_data.get("confidence", 0)
                rationale = judgment_data.get("rationale", "No rationale provided")

                # Handle potential nested structure
                if isinstance(verdict, dict):
                    verdict = "NOT_FOUND"

                # Ensure confidence is numeric
                if isinstance(confidence_raw, (int, float)):
                    confidence = int(confidence_raw)
                elif isinstance(confidence_raw, str):
                    try:
                        confidence = int(float(confidence_raw))
                    except (ValueError, TypeError):
                        confidence = 0
                else:
                    confidence = 0

                # Combine results
                verified_claim = {
                    **claim,
                    "verdict": verdict,
                    "confidence": confidence,
                    "rationale": rationale,
                    "citations": citation_data.get("citations", [])
                }
                verified_claims.append(verified_claim)

                # Final result summary for this claim
                final_verdict_color = {
                    "SUPPORTED": Fore.GREEN,
                    "CONTRADICTED": Fore.RED,
                    "PARTIAL": Fore.YELLOW,
                    "NOT_FOUND": Fore.BLUE
                }.get(verdict, Fore.WHITE)

                print(f"\n  {Fore.WHITE}Final Result:{Style.RESET_ALL}")
                print(f"    {final_verdict_color}[{verdict}] {confidence}% confidence{Style.RESET_ALL}")

                # Update progress bar for completed claim
                self._print_progress_bar(i+1, total_claims, "Overall Progress")
                print()  # Empty line for readability

            # Step 3: Aggregate results into final structure
            print(f"\n{Fore.GREEN}BUILDING FINAL REPORT{Style.RESET_ALL}")
            self._print_box(
                "STEP 3: REPORT GENERATION",
                ["Aggregating results and generating final report..."],
                Fore.GREEN
            )

            # Group claims by category into blocks
            blocks = {}
            for claim in verified_claims:
                category = claim.get('category', 'General')
                if category not in blocks:
                    blocks[category] = {
                        "block_id": f"block-{len(blocks)+1:02d}",
                        "title": f"Block: {category}",
                        "description": f"Claims related to {category.lower()}",
                        "details": {"pageRange": [1, 50]},
                        "priority": "high",
                        "status": "completed",
                        "claims": []
                    }

                # Convert claim to final format
                final_claim = {
                    "claim_id": claim.get('claim_id'),
                    "title": f"Claim: {claim.get('claim_text', '')[:50]}...",
                    "description": claim.get('claim_text', ''),
                    "details": {
                        "claimText": claim.get('claim_text', ''),
                        "targetLocator": claim.get('target_locator', {}),
                        "verdict": claim.get('verdict', 'NOT_FOUND'),
                        "confidence": claim.get('confidence', 0),
                        "rationale": claim.get('rationale', ''),
                        "citations": claim.get('citations', [])
                    },
                    "priority": "high",
                    "dependencies": [],
                    "status": "completed"
                }
                blocks[category]["claims"].append(final_claim)

            # Create final result structure
            result_data = {
                "document_id": session_id,
                "title": f"{target_file} Verification vs Sources",
                "description": f"Target: {target_file} is verified against source documents",
                "details": {
                    "sourceDocuments": [
                        {"docId": filename, "version": 1, "kind": "source_document"}
                        for filename in source_documents.keys()
                    ]
                },
                "priority": "high",
                "dependencies": [],
                "status": "completed",
                "blocks": list(blocks.values()),
                "audit": {
                    "createdBy": "strands-verifier",
                    "createdAt": datetime.now().isoformat(),
                    "reviewStage": "automated",
                    "notes": "Automated verification using multi-agent analysis"
                }
            }

            # Save result
            self._log_step("Processing verification results...", "INFO")
            result_path = f"{self.config.results_dir}/{session_id}.json"

            # Calculate performance metrics
            end_time = time.time()
            total_time = end_time - start_time

            # Add performance data to result
            result_data["performance"] = {
                "total_time_seconds": round(total_time, 2),
                "claims_processed": len(verified_claims),
                "avg_time_per_claim": round(total_time / max(len(verified_claims), 1), 2),
                "caching_enabled": self.config.enable_caching
            }

            # Save the assembled result
            save_json_result(result_data, result_path)

            # Performance summary with fancy UI
            print(f"\n{Fore.GREEN}VERIFICATION COMPLETE{Style.RESET_ALL}")

            # Count verdicts for summary
            verdict_counts = {"SUPPORTED": 0, "CONTRADICTED": 0, "PARTIAL": 0, "NOT_FOUND": 0}
            for claim in verified_claims:
                verdict = claim.get("verdict", "NOT_FOUND")
                verdict_counts[verdict] = verdict_counts.get(verdict, 0) + 1

            self._print_box(
                "VERIFICATION SUMMARY",
                [
                    f"Total Claims: {len(verified_claims)}",
                    f"Supported: {verdict_counts['SUPPORTED']}",
                    f"Contradicted: {verdict_counts['CONTRADICTED']}",
                    f"Partial: {verdict_counts['PARTIAL']}",
                    f"Not Found: {verdict_counts['NOT_FOUND']}",
                    "",
                    f"Total Time: {total_time:.2f}s",
                    f"Avg/Claim: {total_time / max(len(verified_claims), 1):.2f}s",
                    f"Results: {result_path}"
                ],
                Fore.GREEN
            )

            return result_path

        except Exception as e:
            print(f"\n{Fore.RED}VERIFICATION FAILED{Style.RESET_ALL}")
            self._print_box(
                "ERROR DETAILS",
                [
                    f"Session: {session_id}",
                    f"Error: {str(e)}",
                    f"Time: {datetime.now().isoformat()}"
                ],
                Fore.RED
            )

            error_result = {
                "document_id": session_id,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
            error_path = f"{self.config.results_dir}/{session_id}_error.json"
            save_json_result(error_result, error_path)
            return error_path