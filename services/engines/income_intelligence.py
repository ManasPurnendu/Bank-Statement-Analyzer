import time
from services.engines.context import StatementContext
from services.engines.statement_validator import StatementValidator
from services.engines.salary_detector import SalaryDetector
from services.engines.employer_analyzer import EmployerAnalyzer
from services.engines.salary_stability import SalaryStabilityEngine
from services.engines.salary_date_consistency import SalaryDateConsistencyEngine
from services.engines.bonus_detector import BonusDetector
from services.engines.emi_detector import EMIDetector
from services.engines.foir_engine import FOIREngine
from services.engines.statement_health import StatementHealthEngine
from services.engines.surplus_engine import SurplusEngine
from services.engines.buffer_engine import BufferEngine
from services.engines.confidence_scoring_engine import ConfidenceScoringEngine

class IncomeIntelligenceOrchestrator:
    """
    The master orchestrator that runs the 12-point V2.3 Income Intelligence Pipeline.
    Passes the context sequentially through each engine.
    """
    
    @staticmethod
    def generate_report(transactions, statement_metadata=None):
        start_time = time.time()
        
        # Initialize Context
        ctx = StatementContext(transactions, statement_metadata)
        
        # Phase 1: Pre-Validation
        StatementValidator.validate_initial(ctx)
        
        # If the file is completely corrupt or has zero txns, abort early
        if ctx.income_classification == "PROCESSING_ERROR":
            return IncomeIntelligenceOrchestrator._build_output(ctx, start_time)
            
        # Phase 2: Base Detection
        SalaryDetector.run(ctx)
        StatementValidator.validate_salary_presence(ctx)
        
        # If it's definitely not salaried, abort heavy calculation
        if ctx.income_classification == "NON_SALARIED":
            return IncomeIntelligenceOrchestrator._build_output(ctx, start_time)
            
        # Phase 3: Advanced Engines
        EmployerAnalyzer.run(ctx)
        SalaryStabilityEngine.run(ctx)
        SalaryDateConsistencyEngine.run(ctx)
        BonusDetector.run(ctx)
        
        EMIDetector.run(ctx)
        FOIREngine.run(ctx)
        
        StatementHealthEngine.run(ctx)
        SurplusEngine.run(ctx)
        BufferEngine.run(ctx)
        
        # Phase 4: Final Scoring
        ConfidenceScoringEngine.run(ctx)
        
        return IncomeIntelligenceOrchestrator._build_output(ctx, start_time)
        
    @staticmethod
    def _build_output(ctx: StatementContext, start_time: float):
        execution_time_ms = round((time.time() - start_time) * 1000, 2)
        
        # Structure the final report for the database
        return {
            "engine_version": "v2.3",
            "data_sufficiency_grade": ctx.data_sufficiency_grade,
            "income_classification": ctx.income_classification,
            "base_salary": ctx.confirmed_salary,
            "fixed_emi_obligations": ctx.total_fixed_obligations,
            "foir_percentage": ctx.foir_percentage,
            "stability_score": ctx.stability_score,
            "statement_health_score": ctx.statement_health_score,
            "surplus_score": ctx.surplus_score,
            "buffer_score": ctx.buffer_score,
            "income_confidence_score": ctx.income_confidence_score,
            "risk_flags": ctx.risk_flags,
            "positive_signals": ctx.positive_signals,
            "calculation_metadata": ctx.calculation_metadata,
            "report_generation_time_ms": execution_time_ms
        }
