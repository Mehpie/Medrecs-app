import { useState, useEffect } from 'react';

const MOCK_DATA = [
  {
    id: 'DART-8821', 
    reference: 'CIV-2023-09A', 
    name: 'Project Vanguard Audit', 
    clientName: 'Acme Corp',
    docsCount: 4092, 
    outputsCount: 15,
    status: 'PROCESSING', 
    lastTelemetry: '2024-10-24 14:22:01 UTC',
    eta: '12m', 
    unread: true, 
    dateMs: 1729779721000, 
    scope: 'me'
  },
  {
    id: 'DART-8790', 
    reference: 'SEC-2024-44X', 
    name: 'Meridian Merger Review', 
    clientName: 'John Doe',
    docsCount: 12844, 
    outputsCount: 42,
    status: 'REVIEW', 
    lastTelemetry: '2024-10-23 09:15:44 UTC',
    eta: null, 
    unread: false, 
    dateMs: 1729674944000, 
    scope: 'firm'
  },
  {
    id: 'DART-8102', 
    reference: 'LIT-2022-11Z', 
    name: 'Estate of J. Sterling', 
    clientName: 'Sterling Trust',
    docsCount: 841, 
    outputsCount: 3,
    status: 'PROCESSING', 
    lastTelemetry: '2024-10-20 16:40:12 UTC',
    eta: '45m', 
    unread: true, 
    dateMs: 1729442412000, 
    scope: 'me'
  },
  {
    id: 'DART-7955', 
    reference: 'INT-2024-01B', 
    name: 'Internal Compliance Q3', 
    clientName: null,
    docsCount: null, 
    outputsCount: 0,
    status: 'CLOSED', 
    lastTelemetry: '', 
    eta: null, 
    unread: false, 
    dateMs: 1729249500000, 
    scope: 'archived'
  },
  {
    id: 'DART-7890', 
    reference: 'CORP-2024-02C', 
    name: 'Q4 Restructuring', 
    clientName: 'Acme Corp',
    docsCount: 215, 
    outputsCount: 1,
    status: 'DRAFT', 
    lastTelemetry: '2024-10-15 08:30:00 UTC',
    eta: null, 
    unread: false, 
    dateMs: 1728981000000, 
    scope: 'firm'
  }
];

// Simulated fetch function
const fetchCases = () => {
  return new Promise((resolve) => {
    setTimeout(() => {
      resolve(MOCK_DATA);
    }, 500);
  });
};

export function useCases() {
  const [data, setData] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let mounted = true;

    const loadData = async () => {
      try {
        setIsLoading(true);
        const result = await fetchCases();
        if (mounted) {
          setData(result);
          setIsLoading(false);
        }
      } catch (err) {
        if (mounted) {
          setError(err);
          setIsLoading(false);
        }
      }
    };

    loadData();

    return () => {
      mounted = false;
    };
  }, []);

  return { data, isLoading, error };
}
