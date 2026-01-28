import { useTranslation } from 'react-i18next';
import { Paper, Typography, Box, Chip, Skeleton, Button } from '@mui/material';
import type { SxProps, Theme } from '@mui/material';
import { Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer } from 'recharts';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import type { PortfolioDiagnosis } from '../../api';

interface PortfolioDiagnosisCardProps {
  diagnosis: PortfolioDiagnosis | null;
  loading: boolean;
  onRefresh: () => void;
  sx?: SxProps<Theme>;
}

const GRADE_COLORS: Record<string, string> = {
  A: '#22c55e',
  B: '#3b82f6',
  C: '#f59e0b',
  D: '#ef4444',
};

export default function PortfolioDiagnosisCard({ diagnosis, loading, onRefresh, sx }: PortfolioDiagnosisCardProps) {
  const { t } = useTranslation();

  if (loading) {
    return (
      <Paper sx={{ p: 2, borderRadius: '12px', ...sx }}>
        <Skeleton width="60%" height={28} />
        <Skeleton variant="circular" width={200} height={200} sx={{ mx: 'auto', my: 2 }} />
        <Skeleton width="80%" />
        <Skeleton width="60%" />
      </Paper>
    );
  }

  if (!diagnosis) {
    return (
      <Paper sx={{ p: 3, borderRadius: '12px', textAlign: 'center', ...sx }}>
        <AutoAwesomeIcon sx={{ fontSize: 48, color: '#6366f1', mb: 1 }} />
        <Typography variant="h6" sx={{ mb: 1 }}>{t('portfolio.ai_diagnosis')}</Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          {t('portfolio.diagnosis_desc')}
        </Typography>
        <Button
          variant="contained"
          onClick={onRefresh}
          startIcon={<AutoAwesomeIcon />}
          sx={{ bgcolor: '#6366f1', '&:hover': { bgcolor: '#4f46e5' }, textTransform: 'none' }}
        >
          {t('portfolio.run_diagnosis')}
        </Button>
      </Paper>
    );
  }

  const dimensions = diagnosis.dimensions || [];
  const recommendations = diagnosis.recommendations || [];
  const totalScore = diagnosis.total_score ?? 0;
  const maxScore = diagnosis.max_score ?? 100;
  const grade = diagnosis.grade || '-';

  const radarData = dimensions.map((d) => ({
    subject: d.name,
    score: d.score,
    fullMark: d.max,
  }));

  return (
    <Paper sx={{ p: 2, borderRadius: '12px', ...sx }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <AutoAwesomeIcon sx={{ color: '#6366f1' }} />
          <Typography variant="h6" sx={{ fontWeight: 600 }}>
            {t('portfolio.ai_diagnosis')}
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Chip
            label={`${grade}`}
            sx={{
              fontWeight: 800,
              fontSize: '1.1rem',
              bgcolor: GRADE_COLORS[grade] || '#94a3b8',
              color: 'white',
              width: 40,
              height: 40,
            }}
          />
          <Typography variant="h5" sx={{ fontWeight: 700, fontFamily: 'JetBrains Mono, monospace' }}>
            {totalScore.toFixed(0)}
            <Typography component="span" variant="body2" color="text.secondary">
              /{maxScore}
            </Typography>
          </Typography>
        </Box>
      </Box>

      <Box sx={{ height: 250 }}>
        <ResponsiveContainer width="100%" height="100%">
          <RadarChart data={radarData}>
            <PolarGrid stroke="#e2e8f0" />
            <PolarAngleAxis dataKey="subject" tick={{ fontSize: 12 }} />
            <PolarRadiusAxis angle={30} domain={[0, 20]} tick={{ fontSize: 10 }} />
            <Radar
              name="Score"
              dataKey="score"
              stroke="#6366f1"
              fill="#6366f1"
              fillOpacity={0.3}
            />
          </RadarChart>
        </ResponsiveContainer>
      </Box>

      {recommendations.length > 0 && (
        <Box sx={{ mt: 2 }}>
          <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 1 }}>
            {t('portfolio.recommendations')}
          </Typography>
          {recommendations.map((rec, idx) => (
            <Box
              key={idx}
              sx={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: 1,
                mb: 0.5,
                p: 1,
                bgcolor: 'action.hover',
                borderRadius: '8px',
              }}
            >
              <Typography variant="body2" sx={{ color: '#f59e0b' }}>•</Typography>
              <Typography variant="body2">{rec}</Typography>
            </Box>
          ))}
        </Box>
      )}

      <Button
        size="small"
        onClick={onRefresh}
        sx={{ mt: 1, textTransform: 'none', color: '#6366f1' }}
      >
        {t('portfolio.refresh_diagnosis')}
      </Button>
    </Paper>
  );
}
