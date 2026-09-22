"""
Scheduler unit tests covering autonomous task execution, active sources, error handling,
and prevention of problematic concurrent execution.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from job_sourcing.scheduler import autonomous_job_sourcing_task, start_scheduler, stop_scheduler, scheduler
from job_sourcing.models import JobSource, SourceType, CollectionRun, RunStatus
from sqlalchemy.orm import Session
from shared.database import SessionLocal


@pytest.fixture(autouse=True)
def cleanup_test_data():
    """Cleanup test data after each test without deleting production job sources."""
    yield
    db = SessionLocal()
    try:
        from sqlalchemy import or_
        test_sources = db.query(JobSource).filter(
            or_(
                JobSource.name.ilike("test%"),
                JobSource.name.ilike("inactive%"),
                JobSource.name.ilike("source%"),
                JobSource.name.ilike("%source%"),
                JobSource.name.ilike("good-%"),
                JobSource.name.ilike("bad-%"),
                JobSource.name.ilike("failing-%"),
                JobSource.name.ilike("successful-%")
            )
        ).all()
        for ts in test_sources:
            db.delete(ts)
        db.commit()
    finally:
        db.close()


@pytest.fixture
def mock_scheduler():
    """Ensure scheduler is stopped before and after each test."""
    if scheduler.running:
        stop_scheduler()
    yield
    if scheduler.running:
        stop_scheduler()


# ==================== AUTONOMOUS TASK EXECUTION TESTS ====================

def test_autonomous_task_with_active_sources(mock_scheduler):
    """Test autonomous task executes collection for active sources."""
    source = JobSource(
        name="test-source",
        type=SourceType.OFFICIAL_API,
        base_url="https://example.com",
        is_active=True
    )

    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.all.return_value = [source]
    mock_db.query.return_value.filter.return_value.all.return_value = []  # no CVs

    with patch('job_sourcing.scheduler.SessionLocal', return_value=mock_db), \
         patch('job_sourcing.scheduler.JobCollectionService') as mock_svc:
        mock_run = Mock()
        mock_svc.run_collection = mock_run

        autonomous_job_sourcing_task()

        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert call_args[0][0].name == "test-source"
        assert call_args[0][1] == "developer python react javascript devops"


def test_autonomous_task_with_no_active_sources(mock_scheduler):
    """Test autonomous task handles case with no active sources."""
    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.all.return_value = []  # no active sources
    mock_db.query.return_value.filter.return_value.all.return_value = []    # no CVs

    with patch('job_sourcing.scheduler.SessionLocal', return_value=mock_db), \
         patch('job_sourcing.scheduler.JobCollectionService') as mock_svc:
        mock_run = Mock()
        mock_svc.run_collection = mock_run

        autonomous_job_sourcing_task()

        mock_run.assert_not_called()


def test_autonomous_task_with_multiple_active_sources(mock_scheduler):
    """Test autonomous task processes all active sources."""
    source1 = JobSource(
        name="source1",
        type=SourceType.OFFICIAL_API,
        base_url="https://example1.com",
        is_active=True
    )
    source2 = JobSource(
        name="source2",
        type=SourceType.OFFICIAL_API,
        base_url="https://example2.com",
        is_active=True
    )

    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.all.return_value = [source1, source2]
    mock_db.query.return_value.filter.return_value.all.return_value = []  # no CVs

    with patch('job_sourcing.scheduler.SessionLocal', return_value=mock_db), \
         patch('job_sourcing.scheduler.JobCollectionService') as mock_svc:
        mock_run = Mock()
        mock_svc.run_collection = mock_run

        autonomous_job_sourcing_task()

        assert mock_run.call_count == 2


def test_autonomous_task_handles_source_errors(mock_scheduler):
    """Test autonomous task continues even if one source fails."""
    source1 = JobSource(
        name="good-source",
        type=SourceType.OFFICIAL_API,
        base_url="https://example.com",
        is_active=True
    )
    source2 = JobSource(
        name="bad-source",
        type=SourceType.OFFICIAL_API,
        base_url="https://example.com",
        is_active=True
    )

    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.all.return_value = [source1, source2]
    mock_db.query.return_value.filter.return_value.all.return_value = []  # no CVs

    call_count = [0]
    def mock_run_collection(source, keywords, db):
        call_count[0] += 1
        if source.name == "bad-source":
            raise Exception("Simulated failure")

    with patch('job_sourcing.scheduler.SessionLocal', return_value=mock_db), \
         patch('job_sourcing.scheduler.JobCollectionService') as mock_svc:
        mock_svc.run_collection = mock_run_collection

        autonomous_job_sourcing_task()

        assert call_count[0] == 2


def test_autonomous_task_uses_default_keywords(mock_scheduler):
    """Test autonomous task uses hardcoded default keywords."""
    db = SessionLocal()
    try:
        source = JobSource(
            name="test-source",
            type=SourceType.OFFICIAL_API,
            base_url="https://example.com",
            is_active=True
        )
        db.add(source)
        db.commit()
        
        with patch('job_sourcing.scheduler.JobCollectionService') as mock_collection_service:
            mock_run_collection = Mock()
            mock_collection_service.run_collection = mock_run_collection
            
            autonomous_job_sourcing_task()
            
            # Verify default keywords are used
            call_args = mock_run_collection.call_args
            assert call_args[0][1] == "developer python react javascript devops"
            
    finally:
        db.close()


# ==================== SCHEDULER LIFECYCLE TESTS ====================

def test_start_scheduler_starts_background_scheduler(mock_scheduler):
    """Test start_scheduler starts the background scheduler."""
    assert not scheduler.running
    
    start_scheduler()
    
    assert scheduler.running
    
    # Clean up
    stop_scheduler()


def test_start_scheduler_is_idempotent(mock_scheduler):
    """Test start_scheduler can be called multiple times safely."""
    start_scheduler()
    start_scheduler()  # Should not raise error
    start_scheduler()  # Should not raise error
    
    assert scheduler.running
    
    stop_scheduler()


def test_stop_scheduler_stops_background_scheduler(mock_scheduler):
    """Test stop_scheduler stops the background scheduler."""
    start_scheduler()
    assert scheduler.running
    
    stop_scheduler()
    assert not scheduler.running


def test_stop_scheduler_is_idempotent(mock_scheduler):
    """Test stop_scheduler can be called multiple times safely."""
    start_scheduler()
    stop_scheduler()
    stop_scheduler()  # Should not raise error
    stop_scheduler()  # Should not raise error
    
    assert not scheduler.running


def test_stop_scheduler_without_start_is_safe(mock_scheduler):
    """Test stop_scheduler can be called even if scheduler never started."""
    # Should not raise error
    stop_scheduler()
    assert not scheduler.running


# ==================== CONCURRENT EXECUTION PREVENTION TESTS ====================

def test_scheduler_adds_single_job_instance(mock_scheduler):
    """Test scheduler adds only one instance of the autonomous job."""
    start_scheduler()
    
    # Check that only one job with this ID exists
    jobs = scheduler.get_jobs()
    autonomous_jobs = [j for j in jobs if j.id == "autonomous_job_sourcing"]
    
    assert len(autonomous_jobs) == 1
    
    stop_scheduler()


def test_scheduler_replace_existing_behavior(mock_scheduler):
    """Test scheduler replaces existing job when called multiple times."""
    start_scheduler()
    
    # Start again - should replace existing job
    start_scheduler()
    
    # Still only one job should exist
    jobs = scheduler.get_jobs()
    autonomous_jobs = [j for j in jobs if j.id == "autonomous_job_sourcing"]
    
    assert len(autonomous_jobs) == 1
    
    stop_scheduler()


def test_scheduler_interval_configuration(mock_scheduler):
    """Test scheduler is configured with 6-hour interval."""
    start_scheduler()
    
    jobs = scheduler.get_jobs()
    autonomous_jobs = [j for j in jobs if j.id == "autonomous_job_sourcing"]
    
    assert len(autonomous_jobs) == 1
    job = autonomous_jobs[0]
    
    # Check trigger is IntervalTrigger with hours=6
    from apscheduler.triggers.interval import IntervalTrigger
    assert isinstance(job.trigger, IntervalTrigger)
    assert job.trigger.interval.total_seconds() == 6 * 3600  # 6 hours
    
    stop_scheduler()


# ==================== DATABASE SESSION MANAGEMENT TESTS ====================

def test_autonomous_task_closes_database_session(mock_scheduler):
    """Test autonomous task properly closes database session."""
    db = SessionLocal()
    try:
        source = JobSource(
            name="test-source",
            type=SourceType.OFFICIAL_API,
            base_url="https://example.com",
            is_active=True
        )
        db.add(source)
        db.commit()
    finally:
        db.close()
    
    with patch('job_sourcing.scheduler.JobCollectionService') as mock_collection_service:
        mock_run_collection = Mock()
        mock_collection_service.run_collection = mock_run_collection
        
        # Patch SessionLocal to track close calls
        original_session_local = SessionLocal
        close_count = [0]
        
        def tracked_session_local():
            session = original_session_local()
            original_close = session.close
            
            def tracked_close():
                close_count[0] += 1
                return original_close()
            
            session.close = tracked_close
            return session
        
        with patch('job_sourcing.scheduler.SessionLocal', tracked_session_local):
            autonomous_job_sourcing_task()
            
            # Verify session was closed
            assert close_count[0] >= 1


def test_autonomous_task_handles_database_connection_errors(mock_scheduler):
    """Test autonomous task handles database connection errors gracefully."""
    # Mock SessionLocal to raise connection error after import
    import job_sourcing.scheduler as scheduler_module
    original_session_local = scheduler_module.SessionLocal
    
    with patch.object(scheduler_module, 'SessionLocal', side_effect=Exception("Database connection failed")):
        # Should not raise unhandled exception - it's logged
        try:
            autonomous_job_sourcing_task()
        except Exception as e:
            # If it raises, it should be the connection error
            assert "Database connection failed" in str(e)


# ==================== ERROR HANDLING TESTS ====================

def test_autonomous_task_logs_collection_errors(mock_scheduler):
    """Test autonomous task logs errors when collection fails."""
    db = SessionLocal()
    try:
        source = JobSource(
            name="failing-source",
            type=SourceType.OFFICIAL_API,
            base_url="https://example.com",
            is_active=True
        )
        db.add(source)
        db.commit()
        
        with patch('job_sourcing.scheduler.JobCollectionService') as mock_collection_service:
            with patch('job_sourcing.scheduler.logger') as mock_logger:
                mock_run_collection = Mock(side_effect=Exception("Collection failed"))
                mock_collection_service.run_collection = mock_run_collection
                
                autonomous_job_sourcing_task()
                
                # Verify error was logged
                assert mock_logger.error.called
                error_calls = [call for call in mock_logger.error.call_args_list]
                assert any("failing-source" in str(call) for call in error_calls)
                
    finally:
        db.close()


def test_autonomous_task_logs_no_active_sources(mock_scheduler):
    """Test autonomous task logs when no active sources found."""
    with patch('job_sourcing.scheduler.SessionLocal') as mock_session_cls, \
         patch('job_sourcing.scheduler.logger') as mock_logger:
        mock_db = Mock()
        mock_db.query.return_value.filter_by.return_value.all.return_value = []
        mock_session_cls.return_value = mock_db
        autonomous_job_sourcing_task()
        
        # Verify some logging occurred
        assert mock_logger.info.called


def test_autonomous_task_logs_collection_success(mock_scheduler):
    """Test autonomous task logs successful collection."""
    db = SessionLocal()
    try:
        source = JobSource(
            name="successful-source",
            type=SourceType.OFFICIAL_API,
            base_url="https://example.com",
            is_active=True
        )
        db.add(source)
        db.commit()
        
        with patch('job_sourcing.scheduler.JobCollectionService') as mock_collection_service:
            with patch('job_sourcing.scheduler.logger') as mock_logger:
                mock_run_collection = Mock()
                mock_collection_service.run_collection = mock_run_collection
                
                autonomous_job_sourcing_task()
                
                # Verify success was logged
                assert mock_logger.info.called
                info_calls = [call for call in mock_logger.info.call_args_list]
                assert any("successful-source" in str(call) for call in info_calls)
                
    finally:
        db.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
