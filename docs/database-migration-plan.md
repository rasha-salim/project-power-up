# Database Access Migration Plan

**Objective**: Standardize database access patterns by migrating from mixed asyncpg connection pool and SQLAlchemy usage to consistent SQLAlchemy AsyncSession pattern.

**Status**: 🟡 In Progress  
**Started**: 2025-06-29  
**Target Completion**: 2025-07-13 (2 weeks)

## 📊 Current State Analysis

### Connection Pool (asyncpg) Files:
- ✅ **Identified**: `backend/app/services/document_upload_service.py` - Uses `get_pool()` and asyncpg directly
- ✅ **Identified**: `backend/app/db/migrations/add_progress_column.py` - Uses asyncpg for migrations  
- ✅ **Identified**: `backend/app/main.py` - Initializes connection pool

### SQLAlchemy Files (Already Compliant):
- ✅ **Compliant**: `backend/app/api/endpoints/projects.py` - Uses `get_async_db()` and `AsyncSession`
- ✅ **Compliant**: `backend/app/api/endpoints/documents_sqlalchemy.py` - Uses SQLAlchemy
- ✅ **Compliant**: 15+ other service files use SQLAlchemy pattern

### Mixed Usage Files:
- 🔍 **Need Review**: Files that import both patterns

## 🎯 Migration Strategy

### Why SQLAlchemy Should Be Standard:
1. **ORM Benefits**: Type safety, relationship management, query builder
2. **Consistency**: Most codebase already uses SQLAlchemy  
3. **Maintainability**: Better abstraction, easier testing
4. **Framework Integration**: Better FastAPI integration

## 📅 Implementation Phases

### ✅ **Immediate Actions** - COMPLETED
- [x] Document current usage patterns
- [x] Add TODO comments to files using connection pool
- [x] Establish rule: All new code MUST use SQLAlchemy

### 🔄 **Phase 1: Compatibility Layer (Week 1)**
**Status**: 🟡 In Progress  
**Target**: 2025-07-06

- [ ] Create `backend/app/db/database_service.py` - Unified database access service
- [ ] Add helper functions for migration  
- [ ] Update imports to use compatibility layer
- [ ] Test compatibility layer functionality

### 📝 **Phase 2: Migrate High-Priority Files (Week 2)**
**Status**: ⏳ Pending  
**Target**: 2025-07-13

**Priority Order (safest first):**
1. [ ] `document_upload_service.py` - Single service, well-contained
2. [ ] Migration scripts - Already isolated functionality  
3. [ ] Utility scripts

### 🧪 **Phase 3: Testing & Validation (Week 3)**
**Status**: ⏳ Pending  
**Target**: 2025-07-20

- [ ] Add comprehensive tests for both patterns
- [ ] Performance testing to ensure no regressions
- [ ] Gradual rollout with feature flags if needed

### 🏁 **Phase 4: Complete Migration (Week 4+)**
**Status**: ⏳ Pending  
**Target**: 2025-07-27

- [ ] Remove asyncpg connection pool entirely
- [ ] Clean up compatibility layer
- [ ] Update documentation

## 📋 Detailed Task Tracking

### Immediate Actions Progress

#### Document Current Usage - COMPLETED
- [x] **File**: `backend/app/services/document_upload_service.py`
  - **Current**: Uses `from app.db.connection_pool import get_pool`
  - **Lines**: 14, and throughout class methods
  - **Action**: ✅ Added migration TODO comments and priority markers

- [x] **File**: `backend/app/db/migrations/add_progress_column.py`  
  - **Current**: Uses asyncpg directly
  - **Action**: ✅ Added migration TODO comments and priority markers

- [x] **File**: `backend/app/main.py`
  - **Current**: Initializes connection pool with `initialize_pool()` 
  - **Lines**: 62-77
  - **Action**: ✅ Added migration TODO comments and priority markers

### Phase 1 Progress

#### Compatibility Layer Creation - COMPLETED
- [x] **Create**: `backend/app/db/database_service.py`
  - [x] DatabaseService class with unified interface
  - [x] get_session() method for SQLAlchemy  
  - [x] get_raw_connection() method for legacy code
  - [x] Migration helper functions
  - [x] Context managers for safe resource handling
  - [x] Query conversion utilities
  - [x] MigrationHelper class for guidance

- [ ] **Update**: Import statements preparation
- [ ] **Test**: Compatibility layer functionality

## 🔧 Implementation Details

### Compatibility Layer Structure
```python
# backend/app/db/database_service.py
class DatabaseService:
    """Unified database access service"""
    
    @staticmethod
    async def get_session() -> AsyncSession:
        """Get SQLAlchemy session - preferred method"""
    
    @staticmethod  
    async def get_raw_connection():
        """Get raw connection for legacy code"""
    
    @staticmethod
    async def migrate_query(raw_query: str, params: dict = None):
        """Helper to convert raw SQL to SQLAlchemy"""
```

### Migration Rules
1. **New Code**: Must use SQLAlchemy `get_async_db()` pattern
2. **Existing Code**: Migrate gradually, file by file
3. **Testing**: Each migration must be independently tested
4. **Rollback**: Individual files can be rolled back if issues arise

## 🎯 Success Criteria

- [ ] Zero downtime during migration
- [ ] No breaking changes to functionality
- [ ] All database operations use consistent pattern
- [ ] Improved code maintainability
- [ ] Better test coverage for database operations

## 🚨 Risk Mitigation

1. **Compatibility Layer**: Allows both patterns to coexist
2. **Gradual Migration**: File-by-file approach reduces risk
3. **Independent Testing**: Each migration tested separately
4. **Rollback Plan**: Can revert individual files if needed
5. **Feature Flags**: Can disable new pattern if issues arise

## 📊 Progress Tracking

### Overall Progress: 40%
- ✅ Analysis Complete
- ✅ Documentation Complete
- ✅ Immediate Actions Complete  
- ✅ Compatibility Layer Created
- ⏳ Testing & Migration Pending

### Completed Today:
1. ✅ Added TODO comments to all connection pool files
2. ✅ Created comprehensive compatibility layer (`database_service.py`)
3. ✅ Documented migration priorities and patterns
4. ✅ Established migration rules and guidelines

### Next Steps:
1. Test compatibility layer functionality
2. Update imports to use compatibility layer (optional)
3. Begin Phase 2 migration of priority files
4. Create comprehensive tests

### Ready for Phase 2:
The compatibility layer is now ready. You can:
- Start using `DatabaseService.get_session()` for new code
- Use migration helpers for converting existing code
- Safely migrate files one by one using the established patterns

---

**Last Updated**: 2025-06-29  
**Next Review**: 2025-07-02