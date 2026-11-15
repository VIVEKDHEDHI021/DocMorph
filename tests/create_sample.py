"""Sample PDF Generator for DocMorph testing and development.

Generates:
1. A realistic 5-page practical report with student details, multiple paragraphs,
   headings, tabular layouts, and footers.
2. A multi-page PDF containing pages without selectable text (image-only and blank)
   for empty-page testing.
3. Encrypted and corrupted PDFs for validation test suites.
"""

from pathlib import Path
import pymupdf


def create_sample_practical_pdf(output_path: Path | str) -> Path:
    """Generates a realistic 5-page selectable-text PDF practical manual.

    Contains:
    - Title, section headings, paragraphs, algorithm comparisons
    - Tabular formatted comparison on Page 4
    - Student details:
        Student Name: Rahul Patel
        Enrollment No: 2300012345
        Roll No: 25
    - Standardized page footers

    Args:
        output_path: Target path to write the PDF.

    Returns:
        Path object pointing to the created PDF.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    doc = pymupdf.open()

    footer_text = "Student Name: Rahul Patel | Enrollment No: 2300012345 | Roll No: 25"

    # --- PAGE 1: Practical 1 - Stack Data Structure ---
    p1 = doc.new_page(width=595, height=842)  # A4 standard dimensions
    p1.insert_text((50, 60), "DEPARTMENT OF COMPUTER ENGINEERING", fontsize=11, fontname="helv")
    p1.insert_text((50, 85), "CS-301: DATA STRUCTURES & ALGORITHMS PRACTICAL MANUAL", fontsize=14, fontname="hebo")
    p1.draw_line((50, 95), (545, 95))

    p1.insert_text((50, 125), "Practical 1: Implementation of Stack using Arrays", fontsize=13, fontname="hebo")
    p1_content = (
        "1. OBJECTIVE AND AIM:\n"
        "To implement a Last-In-First-Out (LIFO) stack data structure using contiguous memory\n"
        "allocation in C/C++, and verify push, pop, and peek operations.\n\n"
        "2. THEORETICAL FOUNDATION:\n"
        "A stack is a fundamental abstract data type that restricts insertion and deletion\n"
        "to a single end, termed the top of the stack. When an element is pushed onto a full\n"
        "stack, an overflow condition is reported. Conversely, attempting to pop from an\n"
        "empty stack triggers an underflow condition.\n\n"
        "3. ALGORITHM SPECIFICATION:\n"
        "Step 1: Initialize stack pointer 'top' = -1.\n"
        "Step 2: In PUSH(x), verify (top < MAX_SIZE - 1); if true, top = top + 1, arr[top] = x.\n"
        "Step 3: In POP(), verify (top >= 0); if true, item = arr[top], top = top - 1, return item.\n"
        "Step 4: In PEEK(), verify (top >= 0); if true, return arr[top] without deletion.\n\n"
        "4. COMPLEXITY ANALYSIS:\n"
        "- Time Complexity: O(1) for PUSH, POP, and PEEK operations.\n"
        "- Auxiliary Space Complexity: O(N) where N represents the static buffer capacity."
    )
    p1.insert_textbox(pymupdf.Rect(50, 135, 545, 750), p1_content, fontsize=10, fontname="helv")
    p1.draw_line((50, 780), (545, 780))
    p1.insert_text((50, 800), f"{footer_text} | Page 1 of 5", fontsize=9, fontname="helv")

    # --- PAGE 2: Practical 2 - Singly Linked List ---
    p2 = doc.new_page(width=595, height=842)
    p2.insert_text((50, 60), "DEPARTMENT OF COMPUTER ENGINEERING", fontsize=11, fontname="helv")
    p2.insert_text((50, 85), "CS-301: DATA STRUCTURES & ALGORITHMS PRACTICAL MANUAL", fontsize=14, fontname="hebo")
    p2.draw_line((50, 95), (545, 95))

    p2.insert_text((50, 125), "Practical 2: Singly Linked List Insertion and Deletion Operations", fontsize=13, fontname="hebo")
    p2_content = (
        "1. OBJECTIVE AND AIM:\n"
        "To construct a singly linked list with dynamic heap node allocation, supporting\n"
        "insertion at the head, insertion at the tail, and arbitrary key deletion.\n\n"
        "2. THEORETICAL FOUNDATION:\n"
        "Unlike fixed arrays, linked lists allocate memory dynamically on demand. Each node\n"
        "contains a data payload and a pointer linking to the successive node in memory.\n"
        "This dynamic allocation eliminates static sizing limitations while introducing\n"
        "pointer dereferencing overhead.\n\n"
        "3. EDGE CASES AND ROBUSTNESS:\n"
        "- Deletion on an empty list: Safely detect null head pointer.\n"
        "- Single-node list deletion: Update head pointer to NULL after freeing memory.\n"
        "- Key not found: Traverse the list to termination without segmentation faults.\n\n"
        "4. SUMMARY OF OPERATIONS:\n"
        "- Insert Head: O(1) time complexity.\n"
        "- Insert Tail: O(N) without tail reference, O(1) with persistent tail pointer.\n"
        "- Search and Delete: O(N) linear scan time."
    )
    p2.insert_textbox(pymupdf.Rect(50, 135, 545, 750), p2_content, fontsize=10, fontname="helv")
    p2.draw_line((50, 780), (545, 780))
    p2.insert_text((50, 800), f"{footer_text} | Page 2 of 5", fontsize=9, fontname="helv")

    # --- PAGE 3: Practical 3 - Binary Search Tree ---
    p3 = doc.new_page(width=595, height=842)
    p3.insert_text((50, 60), "DEPARTMENT OF COMPUTER ENGINEERING", fontsize=11, fontname="helv")
    p3.insert_text((50, 85), "CS-301: DATA STRUCTURES & ALGORITHMS PRACTICAL MANUAL", fontsize=14, fontname="hebo")
    p3.draw_line((50, 95), (545, 95))

    p3.insert_text((50, 125), "Practical 3: Binary Search Tree (BST) Construction & Traversal", fontsize=13, fontname="hebo")
    p3_content = (
        "1. OBJECTIVE AND AIM:\n"
        "To build a Binary Search Tree (BST) and execute In-Order, Pre-Order, and\n"
        "Post-Order tree traversal algorithms.\n\n"
        "2. THEORETICAL PRINCIPLES:\n"
        "In a valid Binary Search Tree, for any given node N:\n"
        "- All elements in the left subtree have values strictly less than key(N).\n"
        "- All elements in the right subtree have values strictly greater than key(N).\n"
        "As a consequence, recursive In-Order traversal yields keys in monotonic ascending order.\n\n"
        "3. TREE TRAVERSAL RECURRENCES:\n"
        "- In-Order: Traverse Left Subtree -> Visit Root -> Traverse Right Subtree.\n"
        "- Pre-Order: Visit Root -> Traverse Left Subtree -> Traverse Right Subtree.\n"
        "- Post-Order: Traverse Left Subtree -> Traverse Right Subtree -> Visit Root.\n\n"
        "4. SEARCH COMPLEXITY:\n"
        "- Average Case: O(log N) depth and lookup time.\n"
        "- Degenerate Case: O(N) when elements are inserted in monotonically sorted order."
    )
    p3.insert_textbox(pymupdf.Rect(50, 135, 545, 750), p3_content, fontsize=10, fontname="helv")
    p3.draw_line((50, 780), (545, 780))
    p3.insert_text((50, 800), f"{footer_text} | Page 3 of 5", fontsize=9, fontname="helv")

    # --- PAGE 4: Practical 4 - Graph Traversal & Tabular Matrix (Distinct Layout) ---
    p4 = doc.new_page(width=595, height=842)
    p4.insert_text((50, 60), "DEPARTMENT OF COMPUTER ENGINEERING", fontsize=11, fontname="helv")
    p4.insert_text((50, 85), "CS-301: DATA STRUCTURES & ALGORITHMS PRACTICAL MANUAL", fontsize=14, fontname="hebo")
    p4.draw_line((50, 95), (545, 95))

    p4.insert_text((50, 125), "Practical 4: Graph Traversal & Algorithm Comparison Matrix", fontsize=13, fontname="hebo")
    p4.insert_text((50, 150), "Comparative benchmark across standard graph algorithms and performance metrics:", fontsize=10, fontname="helv")

    # Tabular presentation of algorithms
    table_header = f"{'Algorithm':<16} {'Time Complexity':<18} {'Space':<10} {'Graph Type':<16} {'Key Application':<20}"
    p4.insert_text((50, 180), table_header, fontsize=9, fontname="cour")
    p4.draw_line((50, 190), (545, 190))

    rows = [
        f"{'BFS':<16} {'O(V + E)':<18} {'O(V)':<10} {'Unweighted':<16} {'Shortest Path':<20}",
        f"{'DFS':<16} {'O(V + E)':<18} {'O(V)':<10} {'Directed/Undir':<16} {'Cycle Detection':<20}",
        f"{'Dijkstra':<16} {'O((V+E) log V)':<18} {'O(V)':<10} {'Non-negative':<16} {'Single-Source Path':<20}",
        f"{'Bellman-Ford':<16} {'O(V * E)':<18} {'O(V)':<10} {'Arbitrary':<16} {'Negative Cycles':<20}",
        f"{'Floyd-Warshall':<16} {'O(V^3)':<18} {'O(V^2)':<10} {'Dense Matrix':<16} {'All-Pairs Shortest':<20}",
        f"{'Kruskal MST':<16} {'O(E log E)':<18} {'O(V)':<10} {'Weighted Undir':<16} {'Spanning Tree':<20}",
    ]

    y_pos = 210
    for r in rows:
        p4.insert_text((50, y_pos), r, fontsize=9, fontname="cour")
        y_pos += 22

    p4.draw_line((50, y_pos + 5), (545, y_pos + 5))

    p4_discussion = (
        "ANALYTICAL DISCUSSION:\n"
        "The empirical matrix above demonstrates that Breadth-First Search (BFS) is optimal\n"
        "for unweighted minimum step exploration, utilizing a FIFO queue. For weighted networks,\n"
        "Dijkstra's priority queue formulation achieves near-linear O((V+E) log V) scalability."
    )
    p4.insert_textbox(pymupdf.Rect(50, y_pos + 25, 545, 750), p4_discussion, fontsize=10, fontname="helv")
    p4.draw_line((50, 780), (545, 780))
    p4.insert_text((50, 800), f"{footer_text} | Page 4 of 5", fontsize=9, fontname="helv")

    # --- PAGE 5: Practical 5 - Sorting Algorithms & Lab Sign-off ---
    p5 = doc.new_page(width=595, height=842)
    p5.insert_text((50, 60), "DEPARTMENT OF COMPUTER ENGINEERING", fontsize=11, fontname="helv")
    p5.insert_text((50, 85), "CS-301: DATA STRUCTURES & ALGORITHMS PRACTICAL MANUAL", fontsize=14, fontname="hebo")
    p5.draw_line((50, 95), (545, 95))

    p5.insert_text((50, 125), "Practical 5: Sorting Algorithms Empirical Analysis & Conclusion", fontsize=13, fontname="hebo")
    p5_content = (
        "1. EMPIRICAL SORTING BENCHMARK:\n"
        "QuickSort, MergeSort, and HeapSort were evaluated on datasets of 100,000 integers.\n"
        "- QuickSort achieved an average runtime of 14.2 milliseconds with median-of-three pivot.\n"
        "- MergeSort demonstrated steady 18.5 ms execution, requiring O(N) secondary storage.\n"
        "- HeapSort achieved 21.0 ms execution in-place with zero secondary allocations.\n\n"
        "2. SEMESTER LABORATORY CONCLUSION:\n"
        "All five prescribed practical exercises have been implemented, profiled, and verified\n"
        "according to curriculum standards. Core asymptotic complexities were confirmed\n"
        "through repeatable empirical benchmarking.\n\n"
        "3. FACULTY VERIFICATION & LAB SIGN-OFF:\n"
        "Faculty Assessment: Completed Satisfactorily\n"
        "Assigned Grade: A+\n"
        "Faculty Signature: Prof. D. Sharma                  Date: 2026-10-31"
    )
    p5.insert_textbox(pymupdf.Rect(50, 135, 545, 750), p5_content, fontsize=10, fontname="helv")
    p5.draw_line((50, 780), (545, 780))
    p5.insert_text((50, 800), f"{footer_text} | Page 5 of 5", fontsize=9, fontname="helv")

    # Set document metadata
    doc.set_metadata({
        "title": "CS-301 Data Structures Practical Manual",
        "author": "Rahul Patel",
        "subject": "Computer Science Lab Practical Submission",
        "creator": "DocMorph Test Suite",
        "producer": "PyMuPDF PDF Generator",
        "creationDate": "D:20261031120000+05'30'",
        "modDate": "D:20261031123000+05'30'",
    })

    doc.save(str(path))
    doc.close()
    return path


def create_empty_page_pdf(output_path: Path | str) -> Path:
    """Generates a PDF with selectable text, image-only, and completely blank pages.

    Page 1: Normal selectable text.
    Page 2: Image-only page (embedded raster pixmap, 0 selectable text).
    Page 3: Completely blank page (0 text, 0 images).

    Args:
        output_path: Target path to write the PDF.

    Returns:
        Path to generated PDF.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    doc = pymupdf.open()

    # Page 1: Selectable text
    p1 = doc.new_page(width=595, height=842)
    p1.insert_text((50, 100), "DocMorph Test Document: Mixed Content Overview", fontsize=14, fontname="hebo")
    p1.insert_text((50, 140), "This page contains standard selectable text for testing purposes.", fontsize=11, fontname="helv")

    # Page 2: Image-only (no selectable text)
    p2 = doc.new_page(width=595, height=842)
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 300, 300), 1)
    p2.insert_image(pymupdf.Rect(100, 100, 400, 400), pixmap=pix)

    # Page 3: Completely blank page (no text, no images)
    doc.new_page(width=595, height=842)

    doc.set_metadata({
        "title": "Mixed Text and Image Test Document",
        "author": "DocMorph QA",
        "subject": "Empty and Image-Only Page Testing",
    })

    doc.save(str(path))
    doc.close()
    return path


def create_encrypted_pdf(output_path: Path | str, password: str = "docmorph123") -> Path:
    """Generates a password-protected encrypted PDF for testing encryption rejection.

    Args:
        output_path: Target file path.
        password: User password for encryption.

    Returns:
        Path to created PDF.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    doc = pymupdf.open()
    p = doc.new_page()
    p.insert_text((50, 100), "Confidential Personal Information - Password Protected", fontsize=12)

    doc.save(
        str(path),
        encryption=pymupdf.PDF_ENCRYPT_AES_256,
        user_pw=password,
        owner_pw="admin_" + password,
    )
    doc.close()
    return path


def create_corrupted_pdf(output_path: Path | str) -> Path:
    """Generates an invalid/corrupted PDF file with broken header and truncated body.

    Args:
        output_path: Target file path.

    Returns:
        Path to created corrupt file.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        f.write(b"%PDF-1.7\n%corrupt truncated content\n<< /Type /Catalog ... broken EOF")
    return path


def create_landscape_practical_pdf(output_path: Path | str) -> Path:
    """Generates a landscape-oriented practical PDF with footer credentials."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    doc = pymupdf.open()
    # Landscape: width=842, height=595
    p = doc.new_page(width=842, height=595)
    p.insert_text((50, 50), "LANDSCAPE PRACTICAL REPORT - ARCHITECTURE & SYSTEMS", fontsize=14, fontname="hebo")
    p.insert_text((50, 100), "This is a landscape document test with wider aspect ratio.", fontsize=11, fontname="helv")
    # Footer placed in bottom 20% (height=595 -> bottom 20% starts at y=476)
    p.draw_line((50, 540), (792, 540))
    p.insert_text(
        (50, 560),
        "Student Name: Rahul Patel | Enrollment No: 2300012345 | Roll No: 25 | Page 1 of 1",
        fontsize=9,
        fontname="helv",
    )
    doc.save(str(path))
    doc.close()
    return path


def create_conflicting_pdf(output_path: Path | str) -> Path:
    """Generates a multi-page PDF with conflicting student names across pages."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    doc = pymupdf.open()

    # Page 1: Student Name: Rahul Patel
    p1 = doc.new_page(width=595, height=842)
    p1.insert_text((50, 50), "PRACTICAL ASSIGNMENT 1", fontsize=14)
    p1.insert_text((50, 800), "Student Name: Rahul Patel | Roll No: 25", fontsize=10)

    # Page 2: Student Name: Rahul Patel
    p2 = doc.new_page(width=595, height=842)
    p2.insert_text((50, 50), "PRACTICAL ASSIGNMENT 2", fontsize=14)
    p2.insert_text((50, 800), "Student Name: Rahul Patel | Roll No: 25", fontsize=10)

    # Page 3: Student Name: Aarav Shah (CONFLICT!)
    p3 = doc.new_page(width=595, height=842)
    p3.insert_text((50, 50), "PRACTICAL ASSIGNMENT 3", fontsize=14)
    p3.insert_text((50, 800), "Student Name: Aarav Shah | Roll No: 25", fontsize=10)

    doc.save(str(path))
    doc.close()
    return path


def create_no_footer_pdf(output_path: Path | str) -> Path:
    """Generates a PDF without any student credentials, containing only general content."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    doc = pymupdf.open()
    p1 = doc.new_page(width=595, height=842)
    p1.insert_text((50, 100), "Theoretical Computer Science Overview", fontsize=14)
    p1.insert_text((50, 150), "General content without student information.", fontsize=11)
    p1.insert_text((50, 800), "Page 1 of 1", fontsize=10)  # Page number only, no personal data

    doc.save(str(path))
    doc.close()
    return path


def create_multiline_field_pdf(output_path: Path | str) -> Path:
    """Generates a PDF where the field label is on one line and value is on the succeeding line."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    doc = pymupdf.open()
    p = doc.new_page(width=595, height=842)
    p.insert_text((50, 100), "Multi-line Student Header/Footer Test", fontsize=14)

    # Multi-line in footer: label at 780, value at 795
    p.insert_text((50, 780), "Student Name:", fontsize=10, fontname="hebo")
    p.insert_text((50, 795), "Rahul Patel", fontsize=10, fontname="helv")

    doc.save(str(path))
    doc.close()
    return path


def create_varied_labels_pdf(output_path: Path | str) -> Path:
    """Generates a PDF testing uppercase, lowercase, dashes, and varied abbreviations."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    doc = pymupdf.open()
    p = doc.new_page(width=595, height=842)
    p.insert_text((50, 100), "Label Variation Test Document", fontsize=14)

    # Varied footer labels:
    # 'NAME OF STUDENT - Rahul Patel'
    # 'ENROLMENT NUMBER: 2300012345'
    # 'Roll Number: 25'
    # 'Student ID: STU20260025'
    footer_str = (
        "NAME OF STUDENT - Rahul Patel | "
        "enrolment number: 2300012345 | "
        "Roll Number: 25 | "
        "Student ID: STU20260025"
    )
    p.insert_text((50, 800), footer_str, fontsize=8, fontname="helv")

    doc.save(str(path))
    doc.close()
    return path


def create_ambiguous_field_pdf(output_path: Path | str) -> Path:
    """Generates a PDF with an empty value for one field and non-standard format for another."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    doc = pymupdf.open()
    p = doc.new_page(width=595, height=842)
    p.insert_text((50, 100), "Ambiguous Field Test Document", fontsize=14)

    # 'Student Name: ' (empty value) and 'Roll No: UNKNOWN_SPECIAL_#999'
    p.insert_text((50, 800), "Student Name: | Roll No: UNKNOWN_SPECIAL_#999", fontsize=9)

    doc.save(str(path))
    doc.close()
    return path


if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parent.parent
    input_dir = base_dir / "input"
    input_dir.mkdir(parents=True, exist_ok=True)

    sample_practical = input_dir / "sample_practical.pdf"
    sample_empty = input_dir / "sample_with_empty_page.pdf"

    print("Generating sample PDFs...")
    create_sample_practical_pdf(sample_practical)
    print(f"Created: {sample_practical}")

    create_empty_page_pdf(sample_empty)
    print(f"Created: {sample_empty}")
    print("Done!")

