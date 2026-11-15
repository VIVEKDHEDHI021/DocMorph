"""DocMorph CLI Entry Point.

Command-line interface supporting:
- Phase 1: Core PDF text extraction & metadata analysis
- Phase 2: Intelligent footer & student credential detection (--detect)
- Phase 3: PDF personalization & text replacement (--name, --enrollment, etc.)
"""

import argparse
import json
import sys
from pathlib import Path

from app.core.exceptions import DocMorphError
from app.schemas.detection_data import FieldType, ReviewStatus
from app.schemas.replacement_data import (
    ReplacementItem,
    ReplacementRequest,
    ReplacementResult,
)
from app.services.detection_engine import DetectionEngine
from app.services.pdf_analyzer import PDFAnalyzer
from app.services.pdf_replacer import PDFReplacer


def build_cli_parser() -> argparse.ArgumentParser:
    """Builds and configures the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="python -m app.main",
        description="DocMorph PDF Engine, Detection, and Personalization CLI",
    )
    parser.add_argument(
        "file",
        type=str,
        nargs="?",
        default=None,
        help="Path to the PDF file to inspect, analyze, or personalize.",
    )
    # Phase 4 Server Mode
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Launch the DocMorph FastAPI REST API backend server.",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Server host address (default: 127.0.0.1).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Server port number (default: 8000).",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload on code changes (development mode).",
    )
    parser.add_argument(
        "--detect",
        action="store_true",
        dest="run_detection",
        help="Run Phase 2 intelligent footer and student personal information detection.",
    )
    # Phase 3 Personalization Options
    parser.add_argument(
        "--name",
        type=str,
        default=None,
        help="Replacement value for student name.",
    )
    parser.add_argument(
        "--enrollment",
        type=str,
        default=None,
        help="Replacement value for enrollment number.",
    )
    parser.add_argument(
        "--roll",
        type=str,
        default=None,
        help="Replacement value for roll number.",
    )
    parser.add_argument(
        "--student-id",
        type=str,
        default=None,
        help="Replacement value for student ID.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="output_json",
        help="Output result in JSON format.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=None,
        help="Optional file path or directory to save output results.",
    )
    return parser


def format_analyzer_output(result) -> str:
    """Formats the Phase 1 PDFAnalysisResult for console display."""
    lines = [
        "========================================",
        "               DOCMORPH",
        "          PDF ANALYSIS ENGINE",
        "========================================",
        "",
        f"File: {result.filename}",
        f"Total Pages: {result.summary.total_pages}",
        f"Pages With Text: {result.summary.pages_with_text}",
        f"Empty Pages: {result.summary.empty_pages}",
        f"Total Characters: {result.summary.total_characters}",
        f"Total Words: {result.summary.total_words}",
        f"Processing Time: {result.summary.processing_duration_formatted}",
        "",
    ]

    for page in result.pages:
        lines.append(f"--------------- PAGE {page.page_number} ---------------")
        lines.append("")
        if page.text:
            lines.append(page.text)
        else:
            lines.append("[No selectable text on this page]")
        lines.append("")

    lines.append("----------------------------------------")
    lines.append("")
    lines.append("PDF analysis completed successfully.")
    return "\n".join(lines)


def format_detection_output(result) -> str:
    """Formats the Phase 2 DetectionResult for console display."""
    lines = [
        "========================================",
        "               DOCMORPH",
        "     INTELLIGENT DETECTION ENGINE",
        "========================================",
        "",
        f"File: {result.filename}",
        f"Document ID: {result.document_id}",
        f"Total Pages: {result.total_pages}",
        f"Fields Detected: {result.detection_summary.total_fields_detected}",
        f"High: {result.detection_summary.high_confidence_count} | "
        f"Medium: {result.detection_summary.medium_confidence_count} | "
        f"Low: {result.detection_summary.low_confidence_count}",
        f"Review Required: {result.detection_summary.review_required_count} | "
        f"Conflicts: {result.detection_summary.conflicts_count}",
        "",
        "--------------- DETECTED FIELDS ---------------",
    ]

    if not result.detected_fields:
        lines.append("")
        lines.append("[No student credentials detected in document footers]")
        lines.append("")
    else:
        for idx, field in enumerate(result.detected_fields, start=1):
            pages_list = sorted(list(set(occ.page_number for occ in field.occurrences)))
            lines.append("")
            lines.append(f"[{idx}] {field.field_type.value} (ID: {field.field_id})")
            lines.append(f"    Value: '{field.suggested_value}'")
            if field.suggested_value != field.original_value:
                lines.append(f"    Original: '{field.original_value}'")
            lines.append(
                f"    Confidence: {field.confidence:.2f} ({field.confidence_level.value.upper()}) | "
                f"Status: {field.status.value} | Review: {field.review_required}"
            )
            lines.append(f"    Occurrences: {len(field.occurrences)} across pages {pages_list}")
            if field.confidence_reasons:
                lines.append("    Reasons:")
                for r in field.confidence_reasons:
                    lines.append(f"      - {r}")

    if result.conflicts:
        lines.append("")
        lines.append("------------------ CONFLICTS -------------------")
        for c in result.conflicts:
            lines.append(f"  * [{c.field_type.value}] {c.description}")

    lines.append("")
    lines.append("----------------------------------------")
    lines.append("")
    lines.append("Intelligent detection completed successfully.")
    return "\n".join(lines)


def format_replacement_output(result: ReplacementResult) -> str:
    """Formats the Phase 3 ReplacementResult for console display."""
    lines = [
        "========================================",
        "               DOCMORPH",
        "     PDF PERSONALIZATION ENGINE",
        "========================================",
        "",
        f"Job ID: {result.job_id}",
        f"Source Document: {result.original_filename}",
        f"Personalized PDF: {result.output_filename}",
        f"Output Location: {result.output_path}",
        f"Fields Replaced: {result.total_successful} / {result.total_requested}",
        f"Occurrences Updated: {result.successful_occurrences} / {result.total_occurrences}",
        f"Verification Status: {result.verification_status.value.upper()}",
        f"Processing Time: {result.processing_duration_formatted}",
        "",
        "------------- REPLACEMENT DETAILS --------------",
    ]

    for occ in result.occurrence_results:
        status_tag = f"[{occ.status.value.upper()}]"
        lines.append(
            f"Page {occ.page_number} {status_tag} {occ.field_id}: "
            f"'{occ.original_value}' -> '{occ.inserted_value}'"
        )
        if occ.warning:
            lines.append(f"   Warning: {occ.warning}")

    if result.warnings:
        lines.append("")
        lines.append("------------------ WARNINGS --------------------")
        for w in result.warnings:
            lines.append(f"  * {w}")

    lines.append("")
    lines.append("----------------------------------------")
    lines.append("")
    lines.append("PDF personalization completed successfully.")
    return "\n".join(lines)


def main() -> int:
    """CLI execution entry point."""
    parser = build_cli_parser()
    args = parser.parse_args()

    if getattr(args, "serve", False):
        import uvicorn

        print("\n========================================")
        print("          DOCMORPH API SERVER")
        print("========================================")
        print(f"Starting server on http://{args.host}:{args.port}")
        print(f"Interactive Swagger Docs: http://{args.host}:{args.port}/docs")
        print("----------------------------------------\n")
        uvicorn.run("app.server:app", host=args.host, port=args.port, reload=args.reload)
        return 0

    if not args.file:
        parser.error("the following arguments are required: file (or specify --serve to launch backend server)")

    try:
        # Determine execution mode: Phase 3 Personalization > Phase 2 Detection > Phase 1 Analysis
        is_personalization = any(
            [args.name, args.enrollment, args.roll, args.student_id]
        )

        if is_personalization:
            # Phase 3: Run detection first, then apply requested personalizations
            engine = DetectionEngine()
            det_res = engine.detect_file(args.file)

            replacement_items: list[ReplacementItem] = []

            # Map CLI flags to recognized field types
            param_map = [
                (FieldType.STUDENT_NAME, args.name),
                (FieldType.ENROLLMENT_NUMBER, args.enrollment),
                (FieldType.ROLL_NUMBER, args.roll),
                (FieldType.STUDENT_ID, args.student_id),
            ]

            for field_type, new_val in param_map:
                if not new_val:
                    continue
                # Find matching field in detection results
                field = next(
                    (f for f in det_res.detected_fields if f.field_type == field_type),
                    None,
                )
                if not field:
                    print(
                        f"[Warning: No {field_type.value} was detected in document footers to replace]"
                    )
                    continue

                # Confirm field for replacement
                field.confirm()
                replacement_items.append(
                    ReplacementItem(
                        field_id=field.field_id,
                        field_type=field_type,
                        original_value=field.original_value,
                        new_value=new_val.strip(),
                        review_status=ReviewStatus.CONFIRMED,
                    )
                )

            if not replacement_items:
                print("\nError: No detected fields matched the provided replacement arguments.")
                return 1

            req = ReplacementRequest(
                document_id=det_res.document_id,
                source_file=args.file,
                replacements=replacement_items,
            )

            replacer = PDFReplacer()
            out_dir = Path(args.output) if (args.output and Path(args.output).is_dir()) else None
            rep_res = replacer.replace_fields(
                source_pdf=args.file,
                detection_result=det_res,
                request=req,
                output_dir=out_dir,
            )

            if args.output_json:
                print(rep_res.model_dump_json(indent=2))
            else:
                print(format_replacement_output(rep_res))

            return 0

        elif args.run_detection:
            # Phase 2: Detection Mode
            engine = DetectionEngine()
            result = engine.detect_file(args.file)
            if args.output_json:
                print(result.model_dump_json(indent=2))
            else:
                print(format_detection_output(result))

            if args.output:
                output_path = Path(args.output)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
                print(f"\n[Saved JSON output to: {output_path}]")

            return 0

        else:
            # Phase 1: Core Text & Metadata Analysis Mode
            analyzer = PDFAnalyzer()
            result = analyzer.analyze(args.file)
            if args.output_json:
                print(result.model_dump_json(indent=2))
            else:
                print(format_analyzer_output(result))

            if args.output:
                output_path = Path(args.output)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
                print(f"\n[Saved JSON output to: {output_path}]")

            return 0

    except DocMorphError as e:
        print("\n========================================")
        print("             DOCMORPH ERROR")
        print("========================================")
        print(f"Error: {e.user_message}")
        print("----------------------------------------\n")
        return 1
    except Exception as e:
        print("\n========================================")
        print("             DOCMORPH ERROR")
        print("========================================")
        print(f"Error: An unexpected failure occurred: {type(e).__name__}")
        print("----------------------------------------\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
