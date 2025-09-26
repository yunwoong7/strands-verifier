from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from src.config import Config
import os

def setup_telemetry(config: Config) -> trace.Tracer:
    """
    Set up OpenTelemetry tracing with Arize integration
    """
    # Create resource with service information
    resource = Resource.create({
        "service.name": "strands-verifier",
        "service.version": "1.0.0",
        "project.name": config.arize_project_name
    })

    # Set up tracer provider
    trace.set_tracer_provider(TracerProvider(resource=resource))
    tracer_provider = trace.get_tracer_provider()

    # Configure OTLP exporter for Arize
    if config.arize_space_id and config.arize_api_key:
        # Set environment variables for Arize
        os.environ["ARIZE_SPACE_ID"] = config.arize_space_id
        os.environ["ARIZE_API_KEY"] = config.arize_api_key

        # For Arize, you would typically use their specific endpoint
        # This is a placeholder - adjust based on Arize's actual OTLP endpoint
        otlp_exporter = OTLPSpanExporter(
            endpoint="https://otlp.arize.com/v1/traces",  # Placeholder endpoint
            headers={
                "space_id": config.arize_space_id,
                "api_key": config.arize_api_key
            }
        )

        span_processor = BatchSpanProcessor(otlp_exporter)
        tracer_provider.add_span_processor(span_processor)

    # Return tracer
    return trace.get_tracer("strands-verifier")

class TelemetryMixin:
    """
    Mixin class to add telemetry capabilities to agents
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tracer = trace.get_tracer("strands-verifier")

    def create_span(self, name: str, attributes: dict = None):
        """Create a new span with optional attributes"""
        span = self.tracer.start_span(name)
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)
        return span