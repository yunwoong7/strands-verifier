#!/usr/bin/env python3
import click
import os
from pathlib import Path
from src.config import Config
from src.orchestrator import DocumentVerificationOrchestrator
from src.telemetry import setup_telemetry
from colorama import Fore, Style, init

# Initialize colorama
init(autoreset=True)

@click.command()
@click.option('--source-dir', default='./source', help='Directory containing source documents (TXT files)')
@click.option('--target-dir', default='./target', help='Directory containing target document (TXT file)')
@click.option('--results-dir', default='./results', help='Directory to save verification results')
@click.option('--session-id', help='Custom session ID for this verification run')
@click.option('--aws-profile', help='AWS profile to use for Bedrock')
@click.option('--aws-region', default='us-west-2', help='AWS region for Bedrock')
@click.option('--arize-space-id', help='Arize space ID for telemetry')
@click.option('--arize-api-key', help='Arize API key for telemetry')
@click.option('--no-cache', is_flag=True, help='Disable caching for performance comparison')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose output')
def verify(source_dir, target_dir, results_dir, session_id, aws_profile, aws_region, arize_space_id, arize_api_key, no_cache, verbose):
    """
    Verify target document against source documents using multi-agent analysis.

    This tool uses Strands SDK with specialized agents to:
    1. Extract claims from target document
    2. Find evidence in source documents
    3. Make verification decisions
    4. Generate citation-backed results
    """
    try:
        # Create directories if they don't exist
        Path(results_dir).mkdir(parents=True, exist_ok=True)
        Path('./traces').mkdir(parents=True, exist_ok=True)

        # Create configuration
        config = Config(
            source_dir=source_dir,
            target_dir=target_dir,
            results_dir=results_dir,
            aws_profile=aws_profile,
            aws_region=aws_region,
            arize_space_id=arize_space_id,
            arize_api_key=arize_api_key,
            enable_caching=not no_cache  # Invert no_cache flag
        )

        if verbose:
            click.echo(f"{Fore.CYAN}Configuration:{Style.RESET_ALL}")
            click.echo(f"  Source Directory: {config.source_dir}")
            click.echo(f"  Target Directory: {config.target_dir}")
            click.echo(f"  Results Directory: {config.results_dir}")
            click.echo(f"  AWS Region: {config.aws_region}")
            click.echo(f"  Model: {config.model_id}")

        # Setup telemetry
        if verbose:
            click.echo(f"{Fore.BLUE}[INFO]{Style.RESET_ALL} Setting up telemetry...")

        tracer = setup_telemetry(config)

        # Check for required directories and files
        if not Path(source_dir).exists():
            raise click.ClickException(f"Source directory '{source_dir}' does not exist")

        if not Path(target_dir).exists():
            raise click.ClickException(f"Target directory '{target_dir}' does not exist")

        source_files = list(Path(source_dir).glob("*.txt"))
        target_files = list(Path(target_dir).glob("*.txt"))

        if not source_files:
            raise click.ClickException(f"No TXT files found in source directory '{source_dir}'")

        if not target_files:
            raise click.ClickException(f"No TXT files found in target directory '{target_dir}'")

        if verbose:
            click.echo(f"{Fore.GREEN}Document Discovery:{Style.RESET_ALL}")
            click.echo(f"  Found {len(source_files)} source document(s)")
            click.echo(f"  Found {len(target_files)} target document(s)")
            click.echo(f"  Target file: {target_files[0].name}")

        # Start verification
        click.echo(f"{Fore.CYAN}[STARTING]{Style.RESET_ALL} Document verification process...")

        with tracer.start_as_current_span("document_verification") as span:
            span.set_attribute("source.file_count", len(source_files))
            span.set_attribute("target.file", str(target_files[0].name))

            if session_id:
                span.set_attribute("session.id", session_id)

            orchestrator = DocumentVerificationOrchestrator(config)
            result_path = orchestrator.verify_document(session_id)

            span.set_attribute("result.path", result_path)

        click.echo(f"{Fore.GREEN}[COMPLETED]{Style.RESET_ALL} Verification finished successfully!")
        click.echo(f"{Fore.BLUE}[RESULT]{Style.RESET_ALL} Results saved to: {result_path}")

        if verbose:
            click.echo(f"\n{Fore.YELLOW}To view results:{Style.RESET_ALL}")
            click.echo(f"  JSON: cat {result_path}")
            click.echo(f"  Table: python main.py view-table {result_path}")
            click.echo(f"  Quick: python main.py view-table {result_path.split('/')[-1]}")

    except Exception as e:
        click.echo(f"{Fore.RED}[ERROR]{Style.RESET_ALL} {str(e)}", err=True)
        raise click.Abort()

@click.command()
@click.argument('result_file')
def view_table(result_file):
    """
    Display verification results in a formatted table view.

    RESULT_FILE: Path to JSON result file or just filename (will look in ./results/)
    """
    from src.table_viewer import load_and_display_results
    from pathlib import Path

    # If just filename provided, look in results directory
    if not '/' in result_file and not result_file.startswith('./'):
        result_file = f"./results/{result_file}"

    if not result_file.endswith('.json'):
        result_file += '.json'

    if not Path(result_file).exists():
        click.echo(f"{Fore.RED}Error: File '{result_file}' not found{Style.RESET_ALL}")
        return

    load_and_display_results(result_file)

@click.group()
def cli():
    """Strands Document Verifier - Multi-Agent Document Verification System"""
    pass

@cli.command()
def init():
    """Initialize project directories and sample files"""
    directories = ['source', 'target', 'results', 'traces']

    for dir_name in directories:
        Path(dir_name).mkdir(exist_ok=True)
        click.echo(f"✅ Created directory: {dir_name}/")

    # Create .env template
    env_template = """# AWS Configuration
AWS_PROFILE=default
AWS_REGION=us-west-2

# Arize Configuration (Optional)
ARIZE_SPACE_ID=your-space-id
ARIZE_API_KEY=your-api-key
"""

    if not Path('.env').exists():
        with open('.env', 'w') as f:
            f.write(env_template)
        click.echo("✅ Created .env template")
    else:
        click.echo("⚠️  .env file already exists")

    click.echo("\n🚀 Project initialized!")
    click.echo("Next steps:")
    click.echo("1. Add TXT files to source/ directory")
    click.echo("2. Add target TXT file to target/ directory")
    click.echo("3. Configure AWS credentials")
    click.echo("4. Run: python main.py verify")

cli.add_command(verify)
cli.add_command(view_table)

if __name__ == '__main__':
    cli()