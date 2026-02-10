#!/usr/bin/env python3
"""
 XML Batch Generator - Generate multiple test reports in a folder

Usage:
    python batch_generator.py ./my_test_reports --count 20
    python batch_generator.py ./my_test_reports --count 50 --groups 30 --nested
    python batch_generator.py ./my_test_reports --count 100 --groups 10 --prefix "daily_"
"""

import xml.etree.ElementTree as ET
import random
import argparse
from datetime import datetime, timedelta
import os


def generate_random_verdict():
    """Generate random verdict with weighted probabilities"""
    r = random.random()
    if r < 0.6:
        return "pass"
    elif r < 0.85:
        return "fail"
    else:
        return "inconclusive"


def generate_test_step(timestamp, step_num, verdict_result):
    """Generate a test step element"""
    step = ET.Element("teststep")
    step.set("timestamp", f"{timestamp:.1f}")
    step.set("level", str(random.randint(0, 2)))
    step.set("type", random.choice(["user", "auto", "system"]))
    step.set("ident", f"TS-{step_num:03d}")

    if verdict_result == "pass":
        step_result = "pass"
    elif verdict_result == "fail" and random.random() < 0.7:
        step_result = "fail"
    else:
        step_result = "pass"

    step.set("result", step_result)

    descriptions = [
        "Initialize diagnostic session",
        "Send request frame",
        "Wait for response",
        "Verify response data",
        "Check timing constraints",
        "Validate checksum",
        "Read DTC memory",
        "Clear DTC status",
        "Switch to extended session",
        "Security access request",
        "Read data by identifier",
        "Write data by identifier",
        "ECU reset",
        "Communication control",
        "Tester present",
        "Control DTC setting",
        "Check voltage level",
        "Measure temperature",
        "Validate signal timing",
        "Check bus load",
        "Verify node availability",
    ]
    step.text = random.choice(descriptions)

    if step_result == "fail" and random.random() < 0.5:
        tabular = ET.SubElement(step, "tabularinfo")
        services = [
            ("ReadDataByIdentifier", "0x22"),
            ("WriteDataByIdentifier", "0x2E"),
            ("ReadDTCInformation", "0x19"),
            ("ClearDiagnosticInformation", "0x14"),
            ("DiagnosticSessionControl", "0x10"),
            ("ECUReset", "0x11"),
            ("SecurityAccess", "0x27"),
            ("CommunicationControl", "0x28"),
            ("TesterPresent", "0x3E"),
            ("ControlDTCSetting", "0x85"),
        ]
        service_name, service_id = random.choice(services)
        error_codes = [
            ("7F 22 78", "0x7F2278", "Response pending timeout"),
            ("7F 22 31", "0x7F2231", "Request out of range"),
            ("7F 27 35", "0x7F2735", "Invalid key"),
            ("7F 31 22", "0x7F3122", "Conditions not correct"),
        ]
        actual_resp, actual_hex, error_desc = random.choice(error_codes)

        rows_data = [
            ["Service", service_name, service_id],
            ["Request", f"{service_id} F1 90", f"0x{service_id[1:]}F190"],
            ["Expected", "62 F1 90 AB CD EF", "0x62F190ABCDEF"],
            ["Actual", actual_resp, actual_hex],
            ["Error", error_desc, f"NRC {actual_resp[-2:]}"],
        ]

        for row_data in rows_data:
            row = ET.SubElement(tabular, "row")
            for cell_data in row_data:
                cell = ET.SubElement(row, "cell")
                cell.text = cell_data

    return step, timestamp + random.uniform(0.5, 2.0)


def generate_test_case(timestamp, case_num, group_name):
    """Generate a test case element"""
    testcase = ET.Element("testcase")
    testcase.set("timestamp", f"{timestamp:.1f}")

    start_time = datetime(2024, 1, 25, 10, 0, 0) + timedelta(seconds=int(timestamp))
    testcase.set("starttime", start_time.strftime("%Y-%m-%d %H:%M:%S"))

    test_types = [
        "UDS",
        "DTC",
        "CAN",
        "Diagnostic",
        "Communication",
        "Memory",
        "Security",
        "Session",
        "Reset",
        "Voltage",
        "Temperature",
        "Timing",
    ]
    test_actions = [
        "Read",
        "Write",
        "Check",
        "Verify",
        "Validate",
        "Test",
        "Monitor",
        "Control",
        "Initialize",
        "Reset",
    ]
    test_targets = [
        "DID",
        "DTC",
        "Memory",
        "Status",
        "Data",
        "Signal",
        "Frame",
        "Service",
        "Session",
        "Access",
    ]

    title = ET.SubElement(testcase, "title")
    title.text = f"{random.choice(test_types)}_{random.choice(test_actions)}_{random.choice(test_targets)}_{case_num:04d}"

    verdict_result = generate_random_verdict()
    num_steps = random.randint(3, 8)
    current_time = timestamp + 0.5

    for step_num in range(1, num_steps + 1):
        step, current_time = generate_test_step(current_time, step_num, verdict_result)
        testcase.append(step)

    verdict = ET.SubElement(testcase, "verdict")
    verdict.set("timestamp", f"{current_time:.1f}")
    verdict.set("result", verdict_result)

    return testcase, current_time + random.uniform(1.0, 3.0)


def generate_skipped_test(timestamp, skip_num):
    """Generate a skipped test element"""
    skipped = ET.Element("skipped")
    title = ET.SubElement(skipped, "title")
    skip_reasons = [
        "Prerequisites_Not_Met",
        "Environment_Not_Ready",
        "HW_Not_Available",
        "SW_Version_Mismatch",
        "Configuration_Missing",
        "Dependency_Failed",
        "Timeout_Prevention",
        "Manual_Execution_Only",
        "Not_Applicable",
    ]
    title.text = f"Skipped_{random.choice(skip_reasons)}_{skip_num:04d}"
    return skipped


def generate_test_group(timestamp, group_num, level=1, max_level=3, nested=True):
    """Generate a test group element"""
    group = ET.Element("testgroup")
    title = ET.SubElement(group, "title")

    group_types = [
        "Communication",
        "Diagnostic",
        "Network",
        "Memory",
        "Security",
        "Session",
        "DTC",
        "UDS",
        "CAN",
        "System",
        "Integration",
        "Functional",
    ]
    group_areas = ["Tests", "Checks", "Validation", "Scenarios", "Cases", "Suite"]

    if isinstance(group_num, int):
        group_num_str = f"{group_num:03d}"
    else:
        group_num_str = str(group_num)

    indent = "  " * (level - 1)
    title.text = f"{indent}Level{level}_{random.choice(group_types)}_{random.choice(group_areas)}_{group_num_str}"

    current_time = timestamp + 1.0
    has_nested = nested and level < max_level and random.random() < 0.3

    if has_nested:
        num_nested = random.randint(1, 3)
        for nested_num in range(1, num_nested + 1):
            nested_group_id = f"{group_num}_{nested_num}"
            nested_group, current_time = generate_test_group(
                current_time, nested_group_id, level + 1, max_level, nested
            )
            group.append(nested_group)
            current_time += random.uniform(2.0, 5.0)
    else:
        num_tests = random.randint(3, 15)
        for test_num in range(1, num_tests + 1):
            if random.random() < 0.1:
                skipped = generate_skipped_test(current_time, test_num)
                group.append(skipped)
            else:
                testcase, current_time = generate_test_case(
                    current_time, test_num, title.text
                )
                group.append(testcase)
            current_time += random.uniform(1.0, 5.0)

    return group, current_time


def generate_test_module(
    num_groups=10, filename="test_report.xml", nested=True, seed=None, file_index=0
):
    """Generate a complete test module with a unique timestamp"""
    if seed is not None:
        random.seed(seed)

    # FIX: Define a unique start time for this specific file
    # We use datetime.now() so every time you run the script, you get new timestamps
    base_start = datetime.now()
    unique_start = base_start + timedelta(minutes=file_index)
    time_str = unique_start.strftime("%Y-%m-%d %H:%M:%S")

    root = ET.Element("testmodule")
    # This 'starttime' is the unique ID for the dashboard database
    root.set("starttime", time_str)
    root.set("timestamp", "0.0")
    root.set("verdicts", "2_basic")
    root.set(
        "measurementid",
        f"{random.randint(10000000, 99999999):08d}-ffff-4444-82aa-af7cs55583",
    )

    testsetup = ET.SubElement(root, "testsetup")
    xinfo = ET.SubElement(testsetup, "xinfo")
    xinfo.set("name", "Test Module Name")
    description = ET.SubElement(xinfo, "description")
    description.text = f"Stress Test Module with {num_groups} Groups"

    current_time = 10.0
    for group_num in range(1, num_groups + 1):
        group, current_time = generate_test_group(
            current_time, group_num, nested=nested
        )
        root.append(group)
        current_time += random.uniform(5.0, 15.0)

    # [Keep your existing indent helper function here]
    def indent(elem, level=0):
        i = "\n" + level * "  "
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = i + "  "
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
            for child in elem:
                indent(child, level + 1)
            if not child.tail or not child.tail.strip():
                child.tail = i
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = i

    indent(root)
    tree = ET.ElementTree(root)
    tree.write(filename, encoding="UTF-8", xml_declaration=True)
    return filename


def main():
    parser = argparse.ArgumentParser(
        description="Generate multiple  XML test reports in a folder"
    )
    parser.add_argument(
        "folder", type=str, help="Output folder path (will be created if not exists)"
    )
    parser.add_argument(
        "--count",
        "-c",
        type=int,
        default=20,
        help="Number of XML files to generate (default: 20)",
    )
    parser.add_argument(
        "--groups",
        "-g",
        type=int,
        default=10,
        help="Number of test groups per file (default: 10)",
    )
    parser.add_argument(
        "--nested", "-n", action="store_true", help="Enable nested test groups"
    )
    parser.add_argument(
        "--prefix",
        "-p",
        type=str,
        default="test_",
        help="Filename prefix (default: test_)",
    )
    parser.add_argument(
        "--seed",
        "-s",
        type=int,
        default=None,
        help="Base random seed (each file gets seed + index)",
    )
    parser.add_argument(
        "--random-groups",
        action="store_true",
        help="Randomize group count per file (between 1 and --groups)",
    )

    args = parser.parse_args()

    # Create output folder
    os.makedirs(args.folder, exist_ok=True)

    print(f"Generating {args.count} XML files in '{args.folder}'...")
    print(
        f"Settings: groups={args.groups}, nested={args.nested}, prefix='{args.prefix}'"
    )
    print("-" * 60)

    generated_files = []

    for i in range(1, args.count + 1):
        # Determine group count
        if args.random_groups:
            num_groups = random.randint(1, args.groups)
        else:
            num_groups = args.groups

        # Generate filename
        filename = f"{args.prefix}{i:03d}.xml"
        filepath = os.path.join(args.folder, filename)

        # Generate file with unique seed if provided
        file_seed = (args.seed + i) if args.seed is not None else None

        generate_test_module(
            num_groups=num_groups,
            filename=filepath,
            nested=args.nested,
            seed=file_seed,
            file_index=i,
        )

        generated_files.append(filepath)
        print(f"[{i:3d}/{args.count}] Generated: {filename} ({num_groups} groups)")

    print("-" * 60)
    print(f"✓ Complete! Generated {len(generated_files)} files in '{args.folder}'")

    # Show total size
    total_size = sum(os.path.getsize(f) for f in generated_files)
    print(f"Total size: {total_size / 1024 / 1024:.2f} MB")


if __name__ == "__main__":
    main()
