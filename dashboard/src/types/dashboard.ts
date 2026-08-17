export type NumericValue = number | string | null;

export interface SourcePeriod {
  start?: string;
  end?: string;
  min?: string;
  max?: string;
  field?: string;
  [key: string]: unknown;
}

export interface DashboardAssumption {
  id?: string;
  title?: string;
  detail?: string;
  [key: string]: unknown;
}

export interface DashboardMetadata {
  generatedAt?: string;
  sourcePeriod?: SourcePeriod | string;
  sourceFiles?: number | string[];
  totalRecords?: NumericValue;
  title?: string;
  orderStatuses?: string[];
  scope?: string;
  privacy?: string;
  assumptions?: Array<DashboardAssumption | string>;
  [key: string]: unknown;
}

export interface ExecutiveCard {
  id?: string;
  label?: string;
  title?: string;
  value?: NumericValue;
  displayValue?: string;
  format?: "currency" | "integer" | "percent" | "decimal" | string;
  unit?: string;
  detail?: string;
  description?: string;
  change?: NumericValue;
  trend?: "up" | "down" | "neutral" | string;
  source?: string;
  [key: string]: unknown;
}

export interface Insight {
  id?: string;
  title?: string;
  text?: string;
  summary?: string;
  detail?: string;
  evidence?: string;
  impact?: string;
  tone?: "positive" | "attention" | "neutral" | string;
  [key: string]: unknown;
}

export interface ExecutiveData {
  cards?: ExecutiveCard[];
  insights?: Array<Insight | string>;
  [key: string]: unknown;
}

export interface MonthlySalesPoint {
  month?: string;
  period?: string;
  date?: string;
  revenue?: NumericValue;
  sales?: NumericValue;
  total?: NumericValue;
  orders?: NumericValue;
  averageTicket?: NumericValue;
  [key: string]: unknown;
}

export interface BreakdownPoint {
  name?: string;
  label?: string;
  channel?: string;
  status?: string;
  value?: NumericValue;
  total?: NumericValue;
  revenue?: NumericValue;
  count?: NumericValue;
  orders?: NumericValue;
  percentage?: NumericValue;
  averageTicket?: NumericValue;
  orderSharePct?: NumericValue;
  revenueSharePct?: NumericValue;
  [key: string]: unknown;
}

export interface SalesData {
  monthly?: MonthlySalesPoint[];
  statuses?: BreakdownPoint[];
  channels?: BreakdownPoint[];
  [key: string]: unknown;
}

export interface EliteCustomer {
  rank?: number;
  customerId?: NumericValue;
  customerLabel?: string;
  label?: string;
  profit?: NumericValue;
  totalProfit?: NumericValue;
  revenue?: NumericValue;
  totalRevenue?: NumericValue;
  orders?: NumericValue;
  orderCount?: NumericValue;
  averageTicket?: NumericValue;
  frequency?: NumericValue;
  categoryDiversity?: NumericValue;
  months?: NumericValue;
  activeMonths?: NumericValue;
  [key: string]: unknown;
}

export interface EligibilityData {
  eligible?: NumericValue;
  eligibleCustomers?: NumericValue;
  total?: NumericValue;
  totalCustomers?: NumericValue;
  registeredCustomers?: NumericValue;
  customersWithOrders?: NumericValue;
  percentage?: NumericValue;
  eligibleSharePct?: NumericValue;
  rule?: string;
  minimumCategories?: NumericValue;
  categoryDistribution?: Array<{
    categories?: NumericValue;
    customers?: NumericValue;
    [key: string]: unknown;
  }>;
  criteria?: string[];
  rules?: string[];
  [key: string]: unknown;
}

export interface CategoryPoint {
  rank?: number;
  category?: string;
  name?: string;
  units?: NumericValue;
  quantity?: NumericValue;
  value?: NumericValue;
  sharePct?: NumericValue;
  [key: string]: unknown;
}

export interface CustomersData {
  eliteTop10?: EliteCustomer[];
  eligibility?: EligibilityData | BreakdownPoint[];
  topEliteCategories?: CategoryPoint[];
  [key: string]: unknown;
}

export interface WeekdayPoint {
  isoWeekday?: number;
  weekday?: string;
  day?: string;
  averageSales?: NumericValue;
  averageDailySales?: NumericValue;
  average?: NumericValue;
  value?: NumericValue;
  days?: NumericValue;
  calendarDays?: NumericValue;
  zeroDays?: NumericValue;
  daysWithoutSales?: NumericValue;
  zeroSalesDays?: NumericValue;
  isLowest?: boolean;
  [key: string]: unknown;
}

export interface ForecastPoint {
  month?: string;
  period?: string;
  forecast?: NumericValue;
  prediction?: NumericValue;
  predicted?: NumericValue;
  actual?: NumericValue;
  realized?: NumericValue;
  error?: NumericValue;
  absoluteError?: NumericValue;
  [key: string]: unknown;
}

export interface ForecastData {
  product?: string;
  model?: string;
  method?: string;
  mae?: NumericValue;
  bias?: NumericValue;
  totalForecast?: NumericValue;
  predictedTotal?: NumericValue;
  totalActual?: NumericValue;
  actualTotal?: NumericValue;
  shortfall?: NumericValue;
  matchingProductRecords?: NumericValue;
  windowMonths?: NumericValue;
  trainPeriod?: SourcePeriod;
  testPeriod?: SourcePeriod;
  points?: ForecastPoint[];
  series?: ForecastPoint[];
  [key: string]: unknown;
}

export interface RecommendationItem {
  rank?: number;
  product?: string;
  name?: string;
  score?: NumericValue;
  similarity?: NumericValue;
  commonCustomers?: NumericValue;
  productCustomers?: NumericValue;
  reason?: string;
  [key: string]: unknown;
}

export interface RecommendationData {
  seedProduct?: string;
  product?: string;
  targetProduct?: string;
  targetCustomers?: NumericValue;
  method?: string;
  items?: RecommendationItem[];
  recommendations?: RecommendationItem[];
  [key: string]: unknown;
}

export interface OperationsData {
  weekdayPos?: WeekdayPoint[];
  forecast?: ForecastData | ForecastPoint[];
  recommendations?: RecommendationData | RecommendationItem[];
  [key: string]: unknown;
}

export interface QualityCheck {
  id?: string;
  label?: string;
  name?: string;
  status?: "pass" | "warning" | "fail" | "info" | string;
  value?: NumericValue;
  detail?: string;
  description?: string;
  [key: string]: unknown;
}

export interface QualitySource {
  name?: string;
  file?: string;
  records?: NumericValue;
  rows?: NumericValue;
  columns?: NumericValue;
  usedForMetrics?: boolean;
  role?: string;
  [key: string]: unknown;
}

export interface PipelineStep {
  id?: string;
  step?: string | number;
  name?: string;
  title?: string;
  label?: string;
  status?: string;
  description?: string;
  detail?: string;
  [key: string]: unknown;
}

export interface QualityData {
  checks?: QualityCheck[];
  sources?: QualitySource[];
  pipeline?: PipelineStep[];
  [key: string]: unknown;
}

export interface DashboardData {
  metadata: DashboardMetadata;
  executive: ExecutiveData;
  sales: SalesData;
  customers: CustomersData;
  operations: OperationsData;
  quality: QualityData;
}

export type DashboardView = "command" | "marina" | "almir" | "gabriel";
