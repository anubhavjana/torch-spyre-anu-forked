#!/usr/bin/env python3
"""
Spyre Dashboard Backend API
Secure proxy for ClickHouse queries - keeps credentials server-side only.

Architecture:
  Frontend (public) → Backend API (private, has secrets) → ClickHouse (private)
"""

import os
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from urllib.parse import urlencode

app = Flask(__name__)
CORS(app)  # Enable CORS for dashboard access

# Configuration from environment variables (injected by K8s)
CH_URL = os.getenv('SPYRE_CH_URL', '')
CH_USER = os.getenv('SPYRE_CH_USER', 'default')
CH_TOKEN = os.getenv('SPYRE_CH_TOKEN', '')
CH_DB = os.getenv('SPYRE_CH_DB', 'spyre')

def execute_clickhouse_query(sql):
    """Execute a ClickHouse query with server-side authentication."""
    if not CH_URL:
        raise ValueError("SPYRE_CH_URL not configured")
    
    params = {
        'database': CH_DB,
        'default_format': 'JSONEachRow',
        'max_result_rows': '100000',
        'result_overflow_mode': 'break',
    }
    
    headers = {
        'Content-Type': 'text/plain',
        'X-ClickHouse-User': CH_USER,
        'X-ClickHouse-Key': CH_TOKEN,
    }
    
    url = f"{CH_URL}?{urlencode(params)}"
    
    try:
        response = requests.post(url, headers=headers, data=sql, timeout=120)
        response.raise_for_status()
        
        text = response.text.strip()
        if not text:
            return []
        
        # Parse JSONEachRow format (one JSON object per line)
        return [json.loads(line) for line in text.split('\n') if line]
    
    except requests.exceptions.RequestException as e:
        raise Exception(f"ClickHouse error: {str(e)}")


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({'status': 'ok', 'service': 'spyre-dashboard-backend'})


@app.route('/api/config', methods=['GET'])
def get_config():
    """Return safe configuration (no secrets)."""
    return jsonify({
        'db': CH_DB,
        'configured': bool(CH_URL),
    })



@app.route('/api/commits', methods=['GET'])
def fetch_commits():
    """Fetch commits list with aggregated test results."""
    try:
        offset = int(request.args.get('offset', 0))
        limit = int(request.args.get('limit', 30))
        branch_filters = request.args.getlist('branch_filter')
        workflow = request.args.get('workflow', '')
        
        # Build branch filter conditions
        branch_conditions = []
        if not branch_filters:
            return jsonify({'data': [], 'count': 0})
        
        if 'push' in branch_filters:
            branch_conditions.append("branch = 'main'")
        if 'merge-queue' in branch_filters:
            branch_conditions.append("startsWith(branch, 'gh-readonly-queue')")
        if 'commit' in branch_filters:
            branch_conditions.append("(branch != 'main' AND NOT startsWith(branch, 'gh-readonly-queue'))")
        
        branch_filter = ' OR '.join(branch_conditions)
        workflow_filter = f"AND workflow = '{workflow.replace(chr(39), chr(92)+chr(39))}'" if workflow else ''
        
        sql = f"""
            SELECT
                commit_sha,
                any(branch) AS branch,
                any(pr_number) AS pr_number,
                count(DISTINCT gha_run_id) AS total_workflows,
                groupArray(DISTINCT workflow) AS workflows,
                sum(passed) AS passed,
                sum(failed) AS failed,
                sum(xfail) AS xfail,
                sum(xpass) AS xpass,
                sum(skipped) AS skipped,
                sum(total_tests) AS total,
                max(triggered_at) AS triggered_at
            FROM (
                SELECT * FROM {CH_DB}.test_runs
                WHERE ({branch_filter}) {workflow_filter}
            )
            GROUP BY commit_sha
            ORDER BY triggered_at DESC
            LIMIT {limit} OFFSET {offset}
        """
        
        results = execute_clickhouse_query(sql.strip())
        return jsonify({'data': results, 'count': len(results)})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/runs', methods=['GET'])
def fetch_runs():
    """Fetch recent test runs."""
    try:
        limit = int(request.args.get('limit', 30))
        workflow = request.args.get('workflow', '')
        
        workflow_filter = f"AND workflow = '{workflow.replace(chr(39), chr(92)+chr(39))}'" if workflow else ''
        
        sql = f"""
            SELECT
                run_id, workflow, suite_name, filename, branch, commit_sha,
                gha_run_id, triggered_at, total_tests, passed, failed,
                skipped, errors, xpass, duration_s
            FROM {CH_DB}.test_runs
            WHERE 1=1 {workflow_filter}
            ORDER BY triggered_at DESC
            LIMIT {limit}
        """
        
        results = execute_clickhouse_query(sql.strip())
        return jsonify({'data': results, 'count': len(results)})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/test-cases/<run_id>', methods=['GET'])
def fetch_test_cases(run_id):
    """Fetch all test cases for a specific run."""
    try:
        # Sanitize run_id
        run_id = run_id.replace("'", "\\'")
        
        case_sql = f"""
            SELECT
                tc.case_id, tc.classname, tc.name, tc.op_name, tc.dtype,
                tc.status, tc.duration_s, tc.fail_message
            FROM {CH_DB}.test_cases tc
            WHERE tc.run_id = '{run_id}'
            ORDER BY tc.classname, tc.name
        """
        
        prop_sql = f"""
            SELECT case_id, prop_name, prop_value
            FROM {CH_DB}.run_properties
            WHERE run_id = '{run_id}'
        """
        
        cases = execute_clickhouse_query(case_sql.strip())
        props = execute_clickhouse_query(prop_sql.strip())
        
        # Group properties by case_id
        props_by_case = {}
        for p in props:
            case_id = p['case_id']
            if case_id not in props_by_case:
                props_by_case[case_id] = []
            props_by_case[case_id].append(p)
        
        # Attach properties to cases
        for case in cases:
            case['properties'] = props_by_case.get(case['case_id'], [])
        
        return jsonify({'data': cases, 'count': len(cases)})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/commit-tests/<commit_sha>', methods=['GET'])
def fetch_commit_tests(commit_sha):
    """Fetch all test cases for a specific commit with branch filtering."""
    try:
        # Sanitize commit_sha
        commit_sha = commit_sha.replace("'", "\\'")
        branch_filters = request.args.getlist('branch_filter')
        
        # Build branch filter
        branch_conditions = []
        if 'push' in branch_filters:
            branch_conditions.append("branch = 'main'")
        if 'merge-queue' in branch_filters:
            branch_conditions.append("startsWith(branch, 'gh-readonly-queue')")
        if 'commit' in branch_filters:
            branch_conditions.append("(branch != 'main' AND NOT startsWith(branch, 'gh-readonly-queue'))")
        
        branch_filter = f"AND ({' OR '.join(branch_conditions)})" if branch_conditions else ''
        
        cases_sql = f"""
            SELECT
                tc.case_id, tc.run_id, tc.classname, tc.name, tc.op_name,
                tc.dtype, tc.status, tc.duration_s, tc.fail_message
            FROM {CH_DB}.test_cases tc
            WHERE tc.run_id IN (
                SELECT run_id FROM {CH_DB}.test_runs
                WHERE commit_sha = '{commit_sha}' {branch_filter}
            )
        """
        
        props_sql = f"""
            SELECT rp.case_id, rp.prop_name, rp.prop_value
            FROM {CH_DB}.run_properties rp
            WHERE rp.run_id IN (
                SELECT run_id FROM {CH_DB}.test_runs
                WHERE commit_sha = '{commit_sha}' {branch_filter}
            )
        """
        
        cases = execute_clickhouse_query(cases_sql.strip())
        props = execute_clickhouse_query(props_sql.strip())
        
        # Group properties by case_id
        props_by_case = {}
        for p in props:
            case_id = p['case_id']
            if case_id not in props_by_case:
                props_by_case[case_id] = []
            props_by_case[case_id].append(p)
        
        # Attach properties to cases
        for case in cases:
            case['properties'] = props_by_case.get(case['case_id'], [])
        
        return jsonify({'data': cases, 'count': len(cases)})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/commits/<commit_sha>', methods=['GET'])
def fetch_commit_aggregated(commit_sha):
    """Fetch aggregated data for a specific commit with branch filtering."""
    try:
        # Sanitize commit_sha
        commit_sha = commit_sha.replace("'", "\\'")
        branch_filters = request.args.getlist('branch_filter')
        
        # Build branch filter
        branch_conditions = []
        if 'push' in branch_filters:
            branch_conditions.append("branch = 'main'")
        if 'merge-queue' in branch_filters:
            branch_conditions.append("startsWith(branch, 'gh-readonly-queue')")
        if 'commit' in branch_filters:
            branch_conditions.append("(branch != 'main' AND NOT startsWith(branch, 'gh-readonly-queue'))")
        
        branch_filter = f"AND ({' OR '.join(branch_conditions)})" if branch_conditions else ''
        
        sql = f"""
            SELECT
                commit_sha,
                groupArray(DISTINCT branch) AS branches,
                any(pr_number) AS pr_number,
                groupArray(DISTINCT workflow) AS workflows,
                groupArray(DISTINCT gha_run_id) AS gha_run_ids,
                sum(passed) AS passed,
                sum(failed) AS failed,
                sum(xfail) AS xfail,
                sum(xpass) AS xpass,
                sum(skipped) AS skipped,
                sum(total_tests) AS total_tests,
                max(triggered_at) AS triggered_at
            FROM {CH_DB}.test_runs
            WHERE commit_sha = '{commit_sha}' {branch_filter}
            GROUP BY commit_sha
        """
        
        results = execute_clickhouse_query(sql.strip())
        return jsonify({'data': results, 'count': len(results)})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    port = int(os.getenv('SERVICE_PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

# Made with Bob
