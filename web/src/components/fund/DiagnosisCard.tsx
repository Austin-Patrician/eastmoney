import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Box,
  Typography,
  CircularProgress,
  Paper,
  Chip,
  IconButton,
  Tooltip,
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import ShieldIcon from '@mui/icons-material/Shield';
import BalanceIcon from '@mui/icons-material/Balance';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import PersonIcon from '@mui/icons-material/Person';
import { Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer } from 'recharts';
import { fetchFundDiagnosis } from '../../api';
import type { FundDiagnosisResponse } from '../../api';
import type { ReactElement } from 'react';

interface DiagnosisCardProps {
  code: string;
  fundName: string;
}

const dimensionIcons: Record<string, ReactElement> = {
  'profitability': <TrendingUpIcon fontSize="small" />,
  'risk_resistance': <ShieldIcon fontSize="small" />,
  'stability': <BalanceIcon fontSize="small" />,
  'timing_ability': <AccessTimeIcon fontSize="small" />,
  'management_exp': <PersonIcon fontSize="small" />,
};

const dimensionColors: Record<string, string> = {
  'profitability': '#22c55e',
  'risk_resistance': '#3b82f6',
  'stability': '#8b5cf6',
  'timing_ability': '#f59e0b',
  'management_exp': '#ec4899',
};

export default function DiagnosisCard({ code, fundName }: DiagnosisCardProps) {
  const { t, i18n } = useTranslation();
  const [data, setData] = useState<FundDiagnosisResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadDiagnosis = async (forceRefresh = false) => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchFundDiagnosis(code, forceRefresh);
      setData(result);
    } catch (err) {
      setError(t('funds.diagnosis.error'));
      console.error('Failed to load fund diagnosis:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDiagnosis();
  }, [code]);

  const getScoreColor = (score: number) => {
    if (score >= 80) return '#22c55e';
    if (score >= 60) return '#3b82f6';
    if (score >= 40) return '#f59e0b';
    return '#ef4444';
  };

  const getGradeColor = (grade: string) => {
    if (grade.startsWith('A')) return '#22c55e';
    if (grade.startsWith('B')) return '#3b82f6';
    if (grade.startsWith('C')) return '#f59e0b';
    return '#ef4444';
  };

  const renderScoreCircle = (score: number, grade: string) => {
    const color = getScoreColor(score);
    const circumference = 2 * Math.PI * 45;
    const strokeDashoffset = circumference * (1 - score / 100);

    return (
      <Box sx={{ position: 'relative', width: 140, height: 140 }}>
        <svg viewBox="0 0 100 100" style={{ width: '100%', height: '100%', transform: 'rotate(-90deg)' }}>
          <circle cx="50" cy="50" r="45" fill="none" stroke="#e2e8f0" strokeWidth="8" />
          <circle
            cx="50" cy="50" r="45" fill="none" stroke={color} strokeWidth="8"
            strokeLinecap="round" strokeDasharray={circumference} strokeDashoffset={strokeDashoffset}
            style={{ transition: 'stroke-dashoffset 0.5s ease-in-out' }}
          />
        </svg>
        <Box sx={{
          position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)',
          textAlign: 'center'
        }}>
          <Typography variant="h4" sx={{ fontWeight: 700, color, fontFamily: 'JetBrains Mono' }}>
            {Math.round(score)}
          </Typography>
          <Chip
            label={grade}
            size="small"
            sx={{
              bgcolor: getGradeColor(grade), color: 'white', fontWeight: 600,
              fontSize: '0.75rem', height: 22
            }}
          />
        </Box>
      </Box>
    );
  };

  if (loading) {
    return (
      <Paper sx={{ p: 3, height: 400, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <CircularProgress />
      </Paper>
    );
  }

  if (error || !data) {
    return (
      <Paper sx={{ p: 3, height: 400 }}>
        <Typography color="error">{error || t('funds.diagnosis.no_data')}</Typography>
      </Paper>
    );
  }

  // Prepare radar chart data
  const radarData = data.dimensions.map(dim => ({
    dimension: i18n.language === 'zh' ? dim.name : dim.name_en,
    score: dim.score,
    fullMark: dim.max,
  }));

  return (
    <Paper sx={{ p: 3 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h6" sx={{ fontWeight: 600 }}>
          {t('funds.diagnosis.title')}
        </Typography>
        <Tooltip title={t('common.refresh')}>
          <IconButton onClick={() => loadDiagnosis(true)} size="small">
            <RefreshIcon />
          </IconButton>
        </Tooltip>
      </Box>

      <Box sx={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
        {/* Score Circle */}
        <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: 160 }}>
          {renderScoreCircle(data.score, data.grade)}
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1, textAlign: 'center' }}>
            {fundName}
          </Typography>
        </Box>

        {/* Radar Chart */}
        <Box sx={{ flex: 1, minWidth: 300, height: 250 }}>
          <ResponsiveContainer width="100%" height="100%">
            <RadarChart data={radarData}>
              <PolarGrid stroke="#e2e8f0" />
              <PolarAngleAxis dataKey="dimension" tick={{ fontSize: 12 }} />
              <PolarRadiusAxis angle={90} domain={[0, 20]} tick={{ fontSize: 10 }} />
              <Radar
                name={t('funds.diagnosis.score')}
                dataKey="score"
                stroke="#3b82f6"
                fill="#3b82f6"
                fillOpacity={0.5}
              />
            </RadarChart>
          </ResponsiveContainer>
        </Box>
      </Box>

      {/* Dimension Details */}
      <Box sx={{ mt: 3, display: 'flex', flexWrap: 'wrap', gap: 2 }}>
        {data.dimensions.map((dim, idx) => {
          const dimKey = ['profitability', 'risk_resistance', 'stability', 'timing_ability', 'management_exp'][idx];
          return (
            <Box
              key={dim.name}
              sx={{
                display: 'flex', alignItems: 'center', gap: 1, px: 2, py: 1,
                bgcolor: 'grey.50', borderRadius: 1, minWidth: 150
              }}
            >
              <Box sx={{ color: dimensionColors[dimKey] || '#64748b' }}>
                {dimensionIcons[dimKey]}
              </Box>
              <Box>
                <Typography variant="caption" color="text.secondary">
                  {i18n.language === 'zh' ? dim.name : dim.name_en}
                </Typography>
                <Typography variant="body2" sx={{ fontWeight: 600, fontFamily: 'JetBrains Mono' }}>
                  {dim.score}/{dim.max}
                </Typography>
              </Box>
            </Box>
          );
        })}
      </Box>

      {/* Analysis Summary */}
      {data.analysis_summary && (
        <Box sx={{ mt: 3, p: 2, bgcolor: 'primary.50', borderRadius: 1, borderLeft: 4, borderColor: 'primary.main' }}>
          <Typography variant="body2" sx={{ mb: 1 }}>
            {data.analysis_summary.recommendation}
          </Typography>
          {data.analysis_summary.strengths.length > 0 && (
            <Typography variant="caption" color="success.main">
              {t('funds.diagnosis.strengths')}: {data.analysis_summary.strengths.join(', ')}
            </Typography>
          )}
          {data.analysis_summary.weaknesses.length > 0 && (
            <Typography variant="caption" color="error.main" sx={{ display: 'block' }}>
              {t('funds.diagnosis.weaknesses')}: {data.analysis_summary.weaknesses.join(', ')}
            </Typography>
          )}
        </Box>
      )}
    </Paper>
  );
}
