import React, { useState, useMemo } from 'react';
import DashboardHeader from './DashboardHeader';
import CaseList from './CaseList';
import EmptyState from './EmptyState';
import DashboardSkeleton from './DashboardSkeleton';
import ErrorState from './ErrorState';
import { useCases } from '../hooks/useCases';

export default function Dashboard({ searchQuery }) {
  const [filter, setFilter] = useState('All Cases');
  const [sort, setSort] = useState('recent');
  
  const { data: cases, isLoading, error: hasError } = useCases();

  const filteredAndSortedCases = useMemo(() => {
    let result = [...cases];

    // Search filter
    if (searchQuery) {
      const lowerQ = searchQuery.toLowerCase();
      result = result.filter(
        (c) => (c.name && c.name.toLowerCase().includes(lowerQ)) || 
               (c.clientName && c.clientName.toLowerCase().includes(lowerQ)) || 
               (c.id && c.id.toLowerCase().includes(lowerQ))
      );
    }

    // Filter toggles based on strictly typed scope tag
    if (filter === 'All Cases') result = result.filter((c) => c.scope !== 'archived');
    if (filter === 'My Cases') result = result.filter((c) => c.scope === 'me');
    if (filter === 'Firm Cases') result = result.filter((c) => c.scope === 'firm');
    if (filter === 'Archived') result = result.filter((c) => c.scope === 'archived');

    // Sort
    if (sort === 'recent') {
      result.sort((a, b) => b.dateMs - a.dateMs);
    } else if (sort === 'name') {
      result.sort((a, b) => (a.name || '').localeCompare(b.name || ''));
    } else if (sort === 'status') {
      result.sort((a, b) => (a.status || '').localeCompare(b.status || ''));
    }

    return result;
  }, [cases, searchQuery, filter, sort]);

  return (
    <>
      <DashboardHeader filter={filter} setFilter={setFilter} sort={sort} setSort={setSort} />
      
      {/* Ledger Container */}
      <div className="w-full">
        {isLoading ? (
          <DashboardSkeleton />
        ) : hasError ? (
          <ErrorState onRetry={() => window.location.reload()} />
        ) : filteredAndSortedCases.length > 0 ? (
          <CaseList cases={filteredAndSortedCases} />
        ) : (
          <EmptyState onAction={() => alert('Create new case...')} />
        )}
      </div>
    </>
  );
}
