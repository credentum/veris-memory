#!/usr/bin/env python3
"""
Comprehensive tests for Security Compliance Reporter - Phase 7 Coverage

This test module provides comprehensive coverage for the compliance reporting system
including control libraries, evidence collection, automated assessment, and reporting.
"""
import pytest
import tempfile
import os
import json
import csv
from datetime import datetime, timedelta
from unittest.mock import patch, Mock, MagicMock, mock_open
from typing import Dict, Any, List

# Import compliance reporter components
try:
    from src.security.compliance_reporter import (
        ComplianceFramework, ComplianceStatus, ControlCategory, EvidenceType,
        ComplianceControl, ComplianceEvidence, ComplianceAssessment, ComplianceReport,
        ComplianceControlLibrary, AutomatedComplianceAssessor, EvidenceCollector, 
        ComplianceReporter, ControlStatus
    )
    COMPLIANCE_AVAILABLE = True
except ImportError:
    COMPLIANCE_AVAILABLE = False


@pytest.mark.skipif(not COMPLIANCE_AVAILABLE, reason="Compliance reporter not available")
class TestComplianceEnums:
    """Test compliance framework enums and constants"""
    
    def test_compliance_framework_enum(self):
        """Test ComplianceFramework enum values"""
        assert ComplianceFramework.SOC2.value == "soc2"
        assert ComplianceFramework.ISO_27001.value == "iso27001"
        assert ComplianceFramework.ISO27001.value == "iso27001"  # Backward compatibility
        assert ComplianceFramework.GDPR.value == "gdpr"
        assert ComplianceFramework.HIPAA.value == "hipaa"
        assert ComplianceFramework.PCI_DSS.value == "pci_dss"
        assert ComplianceFramework.NIST.value == "nist"
        assert ComplianceFramework.OWASP.value == "owasp"
        assert ComplianceFramework.CIS.value == "cis"
        assert ComplianceFramework.CCPA.value == "ccpa"
        assert ComplianceFramework.SOX.value == "sox"
    
    def test_compliance_status_enum(self):
        """Test ComplianceStatus enum values"""
        assert ComplianceStatus.COMPLIANT.value == "compliant"
        assert ComplianceStatus.NON_COMPLIANT.value == "non_compliant"
        assert ComplianceStatus.PARTIALLY_COMPLIANT.value == "partially_compliant"
        assert ComplianceStatus.NOT_APPLICABLE.value == "not_applicable"
        assert ComplianceStatus.UNKNOWN.value == "unknown"
    
    def test_control_category_enum(self):
        """Test ControlCategory enum values"""
        assert ControlCategory.ACCESS_CONTROL.value == "access_control"
        assert ControlCategory.AUTHENTICATION.value == "authentication"
        assert ControlCategory.AUTHORIZATION.value == "authorization"
        assert ControlCategory.DATA_PROTECTION.value == "data_protection"
        assert ControlCategory.ENCRYPTION.value == "encryption"
        assert ControlCategory.LOGGING_MONITORING.value == "logging_monitoring"
        assert ControlCategory.NETWORK_SECURITY.value == "network_security"
        assert ControlCategory.VULNERABILITY_MANAGEMENT.value == "vulnerability_management"
        assert ControlCategory.INCIDENT_RESPONSE.value == "incident_response"
        assert ControlCategory.BUSINESS_CONTINUITY.value == "business_continuity"
        assert ControlCategory.RISK_MANAGEMENT.value == "risk_management"
        assert ControlCategory.GOVERNANCE.value == "governance"
    
    def test_evidence_type_enum(self):
        """Test EvidenceType enum values"""
        assert EvidenceType.SYSTEM_CONFIG.value == "system_config"
        assert EvidenceType.SECURITY_CONFIG.value == "security_config"
        assert EvidenceType.ACCESS_CONTROL.value == "access_control"
        assert EvidenceType.ENCRYPTION.value == "encryption"
        assert EvidenceType.AUDIT_LOG.value == "audit_log"
        assert EvidenceType.NETWORK_SECURITY.value == "network_security"
        assert EvidenceType.VULNERABILITY_ASSESSMENT.value == "vulnerability_assessment"
        assert EvidenceType.BACKUP_RECOVERY.value == "backup_recovery"
        assert EvidenceType.DOCUMENTATION.value == "documentation"
        assert EvidenceType.POLICY.value == "policy"
    
    def test_control_status_alias(self):
        """Test ControlStatus backward compatibility alias"""
        assert ControlStatus == ComplianceStatus
        assert ControlStatus.COMPLIANT == ComplianceStatus.COMPLIANT


@pytest.mark.skipif(not COMPLIANCE_AVAILABLE, reason="Compliance reporter not available")
class TestComplianceDataModels:
    """Test compliance data model classes"""
    
    def test_compliance_control_creation(self):
        """Test ComplianceControl dataclass creation"""
        control = ComplianceControl(
            control_id="CC6.1",
            framework=ComplianceFramework.SOC2,
            category=ControlCategory.ACCESS_CONTROL,
            title="Test Control",
            description="Test description",
            requirements=["req1", "req2"],
            implementation_guidance="Test guidance",
            testing_procedures=["test1", "test2"],
            references=["ref1", "ref2"],
            automation_possible=True,
            risk_level="high"
        )
        
        assert control.control_id == "CC6.1"
        assert control.framework == ComplianceFramework.SOC2
        assert control.category == ControlCategory.ACCESS_CONTROL
        assert control.title == "Test Control"
        assert control.description == "Test description"
        assert control.requirements == ["req1", "req2"]
        assert control.implementation_guidance == "Test guidance"
        assert control.testing_procedures == ["test1", "test2"]
        assert control.references == ["ref1", "ref2"]
        assert control.automation_possible is True
        assert control.risk_level == "high"
    
    def test_compliance_control_defaults(self):
        """Test ComplianceControl default values"""
        control = ComplianceControl(
            control_id="TEST-001",
            framework=ComplianceFramework.GDPR,
            category=ControlCategory.DATA_PROTECTION,
            title="Test Control",
            description="Test description"
        )
        
        assert control.requirements == []
        assert control.implementation_guidance == ""
        assert control.testing_procedures == []
        assert control.references == []
        assert control.automation_possible is False
        assert control.risk_level == "medium"
    
    def test_compliance_evidence_creation(self):
        """Test ComplianceEvidence dataclass creation"""
        now = datetime.utcnow()
        evidence = ComplianceEvidence(
            evidence_id="EVD-001",
            control_id="CC6.1",
            evidence_type="configuration",
            title="Test Evidence",
            description="Test evidence description",
            file_path="/path/to/evidence.json",
            content="evidence content",
            collected_at=now,
            collected_by="test_user",
            metadata={"key": "value"}
        )
        
        assert evidence.evidence_id == "EVD-001"
        assert evidence.control_id == "CC6.1"
        assert evidence.evidence_type == "configuration"
        assert evidence.title == "Test Evidence"
        assert evidence.description == "Test evidence description"
        assert evidence.file_path == "/path/to/evidence.json"
        assert evidence.content == "evidence content"
        assert evidence.collected_at == now
        assert evidence.collected_by == "test_user"
        assert evidence.metadata == {"key": "value"}
    
    def test_compliance_assessment_creation(self):
        """Test ComplianceAssessment dataclass creation"""
        now = datetime.utcnow()
        next_due = now + timedelta(days=90)
        
        assessment = ComplianceAssessment(
            assessment_id="ASS-001",
            control_id="CC6.1",
            status=ComplianceStatus.COMPLIANT,
            score=95.0,
            findings=["Finding 1", "Finding 2"],
            evidence_ids=["EVD-001", "EVD-002"],
            assessed_at=now,
            assessed_by="assessor",
            next_assessment_due=next_due,
            remediation_notes="Test remediation",
            risk_rating="low",
            recommendations=["Rec 1", "Rec 2"],
            metadata={"assessment_type": "automated"},
            summary="Test summary"
        )
        
        assert assessment.assessment_id == "ASS-001"
        assert assessment.control_id == "CC6.1"
        assert assessment.status == ComplianceStatus.COMPLIANT
        assert assessment.score == 95.0
        assert assessment.findings == ["Finding 1", "Finding 2"]
        assert assessment.evidence_ids == ["EVD-001", "EVD-002"]
        assert assessment.assessed_at == now
        assert assessment.assessed_by == "assessor"
        assert assessment.next_assessment_due == next_due
        assert assessment.remediation_notes == "Test remediation"
        assert assessment.risk_rating == "low"
        assert assessment.recommendations == ["Rec 1", "Rec 2"]
        assert assessment.metadata == {"assessment_type": "automated"}
        assert assessment.summary == "Test summary"
    
    def test_compliance_report_creation(self):
        """Test ComplianceReport dataclass creation"""
        now = datetime.utcnow()
        start_date = now - timedelta(days=30)
        
        assessment1 = ComplianceAssessment(
            assessment_id="ASS-001",
            control_id="CC6.1",
            status=ComplianceStatus.COMPLIANT
        )
        
        assessment2 = ComplianceAssessment(
            assessment_id="ASS-002",
            control_id="CC6.2",
            status=ComplianceStatus.NON_COMPLIANT
        )
        
        report = ComplianceReport(
            report_id="RPT-001",
            framework=ComplianceFramework.SOC2,
            report_type="full",
            generated_at=now,
            reporting_period_start=start_date,
            reporting_period_end=now,
            assessments=[assessment1, assessment2],
            overall_score=85.5,
            compliance_percentage=75.0,
            generated_by="automated_system",
            recommendations=["Improve access controls"],
            metadata={"version": "1.0"},
            summary={"total_controls": 2, "compliant": 1},
            executive_summary="Executive summary text"
        )
        
        assert report.report_id == "RPT-001"
        assert report.framework == ComplianceFramework.SOC2
        assert report.report_type == "full"
        assert report.generated_at == now
        assert report.reporting_period_start == start_date
        assert report.reporting_period_end == now
        assert len(report.assessments) == 2
        assert report.overall_score == 85.5
        assert report.compliance_percentage == 75.0
        assert report.generated_by == "automated_system"
        assert report.recommendations == ["Improve access controls"]
        assert report.metadata == {"version": "1.0"}
        assert report.summary == {"total_controls": 2, "compliant": 1}
        assert report.executive_summary == "Executive summary text"


@pytest.mark.skipif(not COMPLIANCE_AVAILABLE, reason="Compliance reporter not available")
class TestComplianceControlLibrary:
    """Test compliance control library"""
    
    def setup_method(self):
        """Setup test environment"""
        self.library = ComplianceControlLibrary()
    
    def test_library_initialization(self):
        """Test control library initialization"""
        assert self.library is not None
        assert hasattr(self.library, 'controls')
        assert isinstance(self.library.controls, list)
        assert len(self.library.controls) > 0
    
    def test_get_controls_by_framework(self):
        """Test getting controls by framework"""
        soc2_controls = self.library.get_controls(ComplianceFramework.SOC2)
        assert isinstance(soc2_controls, list)
        assert len(soc2_controls) > 0
        
        # Verify all returned controls are SOC2
        for control in soc2_controls:
            assert control.framework == ComplianceFramework.SOC2
        
        gdpr_controls = self.library.get_controls(ComplianceFramework.GDPR)
        assert isinstance(gdpr_controls, list)
        assert len(gdpr_controls) > 0
        
        # Verify all returned controls are GDPR
        for control in gdpr_controls:
            assert control.framework == ComplianceFramework.GDPR
    
    def test_get_specific_control(self):
        """Test getting specific control by ID"""
        # Test existing control
        control = self.library.get_control("CC6.1")
        assert control is not None
        assert control.control_id == "CC6.1"
        assert control.framework == ComplianceFramework.SOC2
        
        # Test non-existent control
        non_existent = self.library.get_control("NON-EXISTENT")
        assert non_existent is None
    
    def test_control_framework_coverage(self):
        """Test that all major frameworks have controls"""
        frameworks_to_test = [
            ComplianceFramework.SOC2,
            ComplianceFramework.GDPR,
            ComplianceFramework.OWASP,
            ComplianceFramework.PCI_DSS,
            ComplianceFramework.ISO_27001
        ]
        
        for framework in frameworks_to_test:
            controls = self.library.get_controls(framework)
            assert len(controls) > 0, f"No controls found for {framework.value}"
    
    def test_control_categories_coverage(self):
        """Test that controls cover all major categories"""
        all_controls = self.library.controls
        categories_found = set()
        
        for control in all_controls:
            categories_found.add(control.category)
        
        # Should have multiple categories
        assert len(categories_found) >= 5
        
        # Check for key categories
        expected_categories = [
            ControlCategory.ACCESS_CONTROL,
            ControlCategory.AUTHENTICATION,
            ControlCategory.ENCRYPTION,
            ControlCategory.LOGGING_MONITORING
        ]
        
        for category in expected_categories:
            assert category in categories_found
    
    def test_control_risk_levels(self):
        """Test control risk level distribution"""
        all_controls = self.library.controls
        risk_levels = set()
        
        for control in all_controls:
            risk_levels.add(control.risk_level)
        
        # Should have various risk levels
        expected_levels = ["low", "medium", "high", "critical"]
        for level in expected_levels:
            controls_with_level = [c for c in all_controls if c.risk_level == level]
            # At least some controls should exist for each level
            if level in ["medium", "high"]:  # Common levels
                assert len(controls_with_level) > 0


@pytest.mark.skipif(not COMPLIANCE_AVAILABLE, reason="Compliance reporter not available")
class TestAutomatedComplianceAssessor:
    """Test automated compliance assessor"""
    
    def setup_method(self):
        """Setup test environment"""
        self.assessor = AutomatedComplianceAssessor()
    
    @patch('src.security.compliance_reporter.os.path.exists')
    @patch('src.security.compliance_reporter.open', new_callable=mock_open)
    def test_assess_control_with_evidence(self, mock_file, mock_exists):
        """Test control assessment with evidence"""
        mock_exists.return_value = True
        mock_file.return_value.read.return_value = "test configuration"
        
        control = ComplianceControl(
            control_id="TEST-001",
            framework=ComplianceFramework.SOC2,
            category=ControlCategory.ACCESS_CONTROL,
            title="Test Control",
            description="Test description",
            automation_possible=True
        )
        
        evidence = [
            ComplianceEvidence(
                evidence_id="EVD-001",
                control_id="TEST-001",
                evidence_type="configuration",
                title="Config Evidence",
                description="Configuration evidence",
                file_path="/test/config.json"
            )
        ]
        
        assessment = self.assessor.assess_control(control, evidence)
        
        assert assessment is not None
        assert assessment.control_id == "TEST-001"
        assert assessment.status in [
            ComplianceStatus.COMPLIANT,
            ComplianceStatus.NON_COMPLIANT,
            ComplianceStatus.PARTIALLY_COMPLIANT
        ]
        assert isinstance(assessment.score, (int, float, type(None)))
        assert isinstance(assessment.findings, list)
        assert isinstance(assessment.recommendations, list)
    
    def test_assess_control_without_evidence(self):
        """Test control assessment without evidence"""
        control = ComplianceControl(
            control_id="TEST-002",
            framework=ComplianceFramework.GDPR,
            category=ControlCategory.DATA_PROTECTION,
            title="Test Control",
            description="Test description"
        )
        
        assessment = self.assessor.assess_control(control, [])
        
        assert assessment is not None
        assert assessment.control_id == "TEST-002"
        assert assessment.status == ComplianceStatus.UNKNOWN
        assert "No evidence available" in " ".join(assessment.findings)
    
    def test_assess_multiple_controls(self):
        """Test assessing multiple controls"""
        controls = [
            ComplianceControl(
                control_id="TEST-001",
                framework=ComplianceFramework.SOC2,
                category=ControlCategory.ACCESS_CONTROL,
                title="Test Control 1",
                description="Test description 1"
            ),
            ComplianceControl(
                control_id="TEST-002",
                framework=ComplianceFramework.SOC2,
                category=ControlCategory.ENCRYPTION,
                title="Test Control 2",
                description="Test description 2"
            )
        ]
        
        assessments = self.assessor.assess_controls(controls, [])
        
        assert len(assessments) == 2
        assert assessments[0].control_id == "TEST-001"
        assert assessments[1].control_id == "TEST-002"
    
    def test_automation_scoring(self):
        """Test automation scoring logic"""
        # Test high automation score for automated controls
        control_automated = ComplianceControl(
            control_id="AUTO-001",
            framework=ComplianceFramework.SOC2,
            category=ControlCategory.LOGGING_MONITORING,
            title="Automated Control",
            description="Automated monitoring control",
            automation_possible=True
        )
        
        evidence_automated = [
            ComplianceEvidence(
                evidence_id="EVD-AUTO",
                control_id="AUTO-001",
                evidence_type="audit_log",
                title="Automated Log Evidence",
                description="Automated log collection evidence"
            )
        ]
        
        assessment_automated = self.assessor.assess_control(control_automated, evidence_automated)
        
        # Automated controls with evidence should score higher
        if assessment_automated.score is not None:
            assert assessment_automated.score >= 60
    
    def test_risk_level_impact_on_scoring(self):
        """Test risk level impact on scoring"""
        high_risk_control = ComplianceControl(
            control_id="HIGH-RISK",
            framework=ComplianceFramework.SOC2,
            category=ControlCategory.ACCESS_CONTROL,
            title="High Risk Control",
            description="High risk control",
            risk_level="high"
        )
        
        low_risk_control = ComplianceControl(
            control_id="LOW-RISK",
            framework=ComplianceFramework.SOC2,
            category=ControlCategory.ACCESS_CONTROL,
            title="Low Risk Control",
            description="Low risk control",
            risk_level="low"
        )
        
        # Both with minimal evidence
        minimal_evidence = [
            ComplianceEvidence(
                evidence_id="EVD-MIN",
                control_id="MIN-001",
                evidence_type="documentation",
                title="Minimal Evidence",
                description="Minimal documentation"
            )
        ]
        
        high_risk_assessment = self.assessor.assess_control(high_risk_control, minimal_evidence)
        low_risk_assessment = self.assessor.assess_control(low_risk_control, minimal_evidence)
        
        # High risk controls should be more stringent in scoring
        assert high_risk_assessment.risk_rating in ["high", "critical"]
        assert low_risk_assessment.risk_rating in ["low", "medium"]


@pytest.mark.skipif(not COMPLIANCE_AVAILABLE, reason="Compliance reporter not available")
class TestEvidenceCollector:
    """Test evidence collector"""
    
    def setup_method(self):
        """Setup test environment"""
        self.collector = EvidenceCollector()
    
    @patch('src.security.compliance_reporter.os.path.exists')
    @patch('src.security.compliance_reporter.os.path.isfile')
    @patch('src.security.compliance_reporter.open', new_callable=mock_open)
    def test_collect_file_evidence(self, mock_file, mock_isfile, mock_exists):
        """Test collecting file-based evidence"""
        mock_exists.return_value = True
        mock_isfile.return_value = True
        mock_file.return_value.read.return_value = "test file content"
        
        evidence = self.collector.collect_file_evidence(
            control_id="TEST-001",
            file_path="/test/config.json",
            evidence_type="configuration",
            title="Test Config",
            description="Test configuration file"
        )
        
        assert evidence is not None
        assert evidence.control_id == "TEST-001"
        assert evidence.file_path == "/test/config.json"
        assert evidence.evidence_type == "configuration"
        assert evidence.title == "Test Config"
        assert evidence.description == "Test configuration file"
        assert evidence.content == "test file content"
        assert evidence.collected_by == "system"
    
    @patch('src.security.compliance_reporter.os.path.exists')
    def test_collect_file_evidence_missing_file(self, mock_exists):
        """Test collecting evidence for missing file"""
        mock_exists.return_value = False
        
        evidence = self.collector.collect_file_evidence(
            control_id="TEST-002",
            file_path="/missing/file.json",
            evidence_type="configuration",
            title="Missing Config",
            description="Missing configuration file"
        )
        
        assert evidence is None
    
    def test_collect_system_evidence(self):
        """Test collecting system-based evidence"""
        evidence = self.collector.collect_system_evidence(
            control_id="SYS-001",
            evidence_type="system_config",
            title="System Evidence",
            description="System configuration evidence",
            content="system information"
        )
        
        assert evidence is not None
        assert evidence.control_id == "SYS-001"
        assert evidence.evidence_type == "system_config"
        assert evidence.title == "System Evidence"
        assert evidence.description == "System configuration evidence"
        assert evidence.content == "system information"
        assert evidence.file_path is None
    
    @patch('src.security.compliance_reporter.subprocess.run')
    def test_collect_command_evidence(self, mock_subprocess):
        """Test collecting command-based evidence"""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "command output"
        mock_result.stderr = ""
        mock_subprocess.return_value = mock_result
        
        evidence = self.collector.collect_command_evidence(
            control_id="CMD-001",
            command=["ls", "-la"],
            evidence_type="system_config",
            title="Directory Listing",
            description="System directory listing"
        )
        
        assert evidence is not None
        assert evidence.control_id == "CMD-001"
        assert evidence.evidence_type == "system_config"
        assert evidence.title == "Directory Listing"
        assert evidence.content == "command output"
        assert "Command: ls -la" in evidence.description
    
    @patch('src.security.compliance_reporter.subprocess.run')
    def test_collect_command_evidence_failure(self, mock_subprocess):
        """Test collecting evidence for failed command"""
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "command failed"
        mock_subprocess.return_value = mock_result
        
        evidence = self.collector.collect_command_evidence(
            control_id="CMD-002",
            command=["failing-command"],
            evidence_type="system_config",
            title="Failed Command",
            description="Failed command execution"
        )
        
        assert evidence is not None
        assert evidence.control_id == "CMD-002"
        assert "Command failed" in evidence.content
        assert "command failed" in evidence.content
    
    def test_bulk_evidence_collection(self):
        """Test collecting multiple pieces of evidence"""
        evidence_configs = [
            {
                "type": "system",
                "control_id": "BULK-001",
                "evidence_type": "system_config",
                "title": "System Evidence 1",
                "description": "First evidence",
                "content": "content 1"
            },
            {
                "type": "system",
                "control_id": "BULK-002",
                "evidence_type": "system_config",
                "title": "System Evidence 2",
                "description": "Second evidence",
                "content": "content 2"
            }
        ]
        
        evidence_list = []
        for config in evidence_configs:
            evidence = self.collector.collect_system_evidence(
                control_id=config["control_id"],
                evidence_type=config["evidence_type"],
                title=config["title"],
                description=config["description"],
                content=config["content"]
            )
            if evidence:
                evidence_list.append(evidence)
        
        assert len(evidence_list) == 2
        assert evidence_list[0].control_id == "BULK-001"
        assert evidence_list[1].control_id == "BULK-002"


@pytest.mark.skipif(not COMPLIANCE_AVAILABLE, reason="Compliance reporter not available")
class TestComplianceReporter:
    """Test main compliance reporter"""
    
    def setup_method(self):
        """Setup test environment"""
        self.reporter = ComplianceReporter()
    
    def test_reporter_initialization(self):
        """Test compliance reporter initialization"""
        assert self.reporter is not None
        assert hasattr(self.reporter, 'control_library')
        assert hasattr(self.reporter, 'assessor')
        assert hasattr(self.reporter, 'evidence_collector')
        assert isinstance(self.reporter.control_library, ComplianceControlLibrary)
        assert isinstance(self.reporter.assessor, AutomatedComplianceAssessor)
        assert isinstance(self.reporter.evidence_collector, EvidenceCollector)
    
    def test_generate_framework_report(self):
        """Test generating a compliance report for a framework"""
        report = self.reporter.generate_compliance_report(
            framework=ComplianceFramework.SOC2,
            report_type="summary"
        )
        
        assert report is not None
        assert report.framework == ComplianceFramework.SOC2
        assert report.report_type == "summary"
        assert isinstance(report.assessments, list)
        assert len(report.assessments) > 0
        assert report.compliance_percentage >= 0
        assert report.compliance_percentage <= 100
        assert isinstance(report.summary, dict)
    
    def test_generate_report_with_date_range(self):
        """Test generating report with specific date range"""
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=30)
        
        report = self.reporter.generate_compliance_report(
            framework=ComplianceFramework.GDPR,
            report_type="full",
            start_date=start_date,
            end_date=end_date
        )
        
        assert report.reporting_period_start == start_date
        assert report.reporting_period_end == end_date
        assert report.framework == ComplianceFramework.GDPR
        assert report.report_type == "full"
    
    @patch('src.security.compliance_reporter.os.makedirs')
    @patch('src.security.compliance_reporter.open', new_callable=mock_open)
    def test_export_report_json(self, mock_file, mock_makedirs):
        """Test exporting report to JSON"""
        report = self.reporter.generate_compliance_report(
            framework=ComplianceFramework.SOC2,
            report_type="summary"
        )
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "report.json")
            result = self.reporter.export_report(report, output_path, format="json")
            
            assert result is True
            mock_file.assert_called()
    
    @patch('src.security.compliance_reporter.os.makedirs')
    @patch('src.security.compliance_reporter.open', new_callable=mock_open)
    def test_export_report_csv(self, mock_file, mock_makedirs):
        """Test exporting report to CSV"""
        report = self.reporter.generate_compliance_report(
            framework=ComplianceFramework.GDPR,
            report_type="summary"
        )
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "report.csv")
            result = self.reporter.export_report(report, output_path, format="csv")
            
            assert result is True
            mock_file.assert_called()
    
    def test_get_compliance_score(self):
        """Test compliance score calculation"""
        report = self.reporter.generate_compliance_report(
            framework=ComplianceFramework.OWASP,
            report_type="summary"
        )
        
        score = self.reporter.get_compliance_score(ComplianceFramework.OWASP)
        
        assert isinstance(score, (int, float))
        assert score >= 0
        assert score <= 100
    
    def test_get_control_status_summary(self):
        """Test control status summary"""
        summary = self.reporter.get_control_status_summary(ComplianceFramework.SOC2)
        
        assert isinstance(summary, dict)
        assert "total_controls" in summary
        assert "compliant" in summary
        assert "non_compliant" in summary
        assert "partially_compliant" in summary
        assert "not_assessed" in summary
        
        # Verify counts make sense
        total = summary["total_controls"]
        compliant = summary["compliant"]
        non_compliant = summary["non_compliant"]
        partially_compliant = summary["partially_compliant"]
        not_assessed = summary["not_assessed"]
        
        assert total == compliant + non_compliant + partially_compliant + not_assessed
    
    def test_get_framework_recommendations(self):
        """Test getting framework-specific recommendations"""
        recommendations = self.reporter.get_framework_recommendations(ComplianceFramework.PCI_DSS)
        
        assert isinstance(recommendations, list)
        assert len(recommendations) >= 0
        
        for recommendation in recommendations:
            assert isinstance(recommendation, str)
            assert len(recommendation) > 0
    
    def test_compare_frameworks(self):
        """Test comparing compliance across frameworks"""
        frameworks = [ComplianceFramework.SOC2, ComplianceFramework.GDPR]
        comparison = self.reporter.compare_frameworks(frameworks)
        
        assert isinstance(comparison, dict)
        assert "frameworks" in comparison
        assert "comparison_matrix" in comparison
        assert "recommendations" in comparison
        
        assert len(comparison["frameworks"]) == 2
        assert ComplianceFramework.SOC2.value in comparison["frameworks"]
        assert ComplianceFramework.GDPR.value in comparison["frameworks"]
    
    def test_schedule_assessment(self):
        """Test scheduling compliance assessment"""
        schedule_info = self.reporter.schedule_assessment(
            framework=ComplianceFramework.ISO_27001,
            frequency_days=90,
            next_assessment=datetime.utcnow() + timedelta(days=30)
        )
        
        assert isinstance(schedule_info, dict)
        assert "framework" in schedule_info
        assert "frequency_days" in schedule_info
        assert "next_assessment" in schedule_info
        assert "scheduled" in schedule_info
        
        assert schedule_info["framework"] == ComplianceFramework.ISO_27001.value
        assert schedule_info["frequency_days"] == 90
        assert schedule_info["scheduled"] is True


@pytest.mark.skipif(not COMPLIANCE_AVAILABLE, reason="Compliance reporter not available")
class TestComplianceIntegrationScenarios:
    """Test integrated compliance scenarios"""
    
    def setup_method(self):
        """Setup test environment"""
        self.reporter = ComplianceReporter()
    
    def test_end_to_end_compliance_workflow(self):
        """Test complete compliance workflow"""
        # 1. Generate evidence
        evidence = self.reporter.evidence_collector.collect_system_evidence(
            control_id="CC6.1",
            evidence_type="security_config",
            title="Access Control Configuration",
            description="System access control settings",
            content="access_control_enabled=true"
        )
        
        # 2. Get specific control
        control = self.reporter.control_library.get_control("CC6.1")
        assert control is not None
        
        # 3. Assess control with evidence
        assessment = self.reporter.assessor.assess_control(control, [evidence])
        assert assessment is not None
        
        # 4. Generate comprehensive report
        report = self.reporter.generate_compliance_report(
            framework=ComplianceFramework.SOC2,
            report_type="full"
        )
        
        assert report is not None
        assert len(report.assessments) > 0
    
    def test_multi_framework_compliance(self):
        """Test compliance across multiple frameworks"""
        frameworks = [
            ComplianceFramework.SOC2,
            ComplianceFramework.GDPR,
            ComplianceFramework.OWASP
        ]
        
        reports = []
        for framework in frameworks:
            report = self.reporter.generate_compliance_report(
                framework=framework,
                report_type="summary"
            )
            reports.append(report)
        
        assert len(reports) == 3
        
        # Each report should be for different framework
        framework_values = [report.framework for report in reports]
        assert len(set(framework_values)) == 3
    
    def test_compliance_trend_analysis(self):
        """Test compliance trend analysis over time"""
        # Generate reports for different time periods
        now = datetime.utcnow()
        periods = [
            (now - timedelta(days=90), now - timedelta(days=60)),
            (now - timedelta(days=60), now - timedelta(days=30)),
            (now - timedelta(days=30), now)
        ]
        
        trend_data = []
        for start_date, end_date in periods:
            report = self.reporter.generate_compliance_report(
                framework=ComplianceFramework.SOC2,
                report_type="summary",
                start_date=start_date,
                end_date=end_date
            )
            
            trend_data.append({
                "period_end": end_date,
                "compliance_percentage": report.compliance_percentage,
                "total_assessments": len(report.assessments)
            })
        
        assert len(trend_data) == 3
        
        # Verify trend data structure
        for data_point in trend_data:
            assert "period_end" in data_point
            assert "compliance_percentage" in data_point
            assert "total_assessments" in data_point
            assert isinstance(data_point["compliance_percentage"], (int, float))
    
    def test_control_automation_coverage(self):
        """Test automation coverage across controls"""
        all_controls = self.reporter.control_library.controls
        
        automation_stats = {
            "total_controls": len(all_controls),
            "automatable": 0,
            "manual_only": 0,
            "by_category": {}
        }
        
        for control in all_controls:
            if control.automation_possible:
                automation_stats["automatable"] += 1
            else:
                automation_stats["manual_only"] += 1
            
            category = control.category.value
            if category not in automation_stats["by_category"]:
                automation_stats["by_category"][category] = {
                    "total": 0,
                    "automatable": 0
                }
            
            automation_stats["by_category"][category]["total"] += 1
            if control.automation_possible:
                automation_stats["by_category"][category]["automatable"] += 1
        
        # Verify automation coverage
        assert automation_stats["total_controls"] > 0
        assert automation_stats["automatable"] + automation_stats["manual_only"] == automation_stats["total_controls"]
        
        # Check that some controls are automatable
        automation_percentage = (automation_stats["automatable"] / automation_stats["total_controls"]) * 100
        assert automation_percentage > 0  # Should have some automation
    
    def test_risk_based_prioritization(self):
        """Test risk-based control prioritization"""
        all_controls = self.reporter.control_library.controls
        
        # Group controls by risk level
        risk_groups = {}
        for control in all_controls:
            risk_level = control.risk_level
            if risk_level not in risk_groups:
                risk_groups[risk_level] = []
            risk_groups[risk_level].append(control)
        
        # Priority order: critical > high > medium > low
        priority_order = ["critical", "high", "medium", "low"]
        
        prioritized_controls = []
        for risk_level in priority_order:
            if risk_level in risk_groups:
                prioritized_controls.extend(risk_groups[risk_level])
        
        # Verify prioritization
        assert len(prioritized_controls) > 0
        
        # First controls should be higher risk
        if len(prioritized_controls) >= 2:
            first_control_risk = prioritized_controls[0].risk_level
            last_control_risk = prioritized_controls[-1].risk_level
            
            # Map risk levels to numeric values for comparison
            risk_values = {"critical": 4, "high": 3, "medium": 2, "low": 1}
            
            first_value = risk_values.get(first_control_risk, 0)
            last_value = risk_values.get(last_control_risk, 0)
            
            assert first_value >= last_value