export interface TechCoverage {
  '2G': boolean
  '3G': boolean
  '4G': boolean
}

export interface OperatorCoverage {
  orange: TechCoverage
  sfr: TechCoverage
  bouygues: TechCoverage
  free: TechCoverage
}

export interface AddressError {
  error: string
}

export type CoverageResult = OperatorCoverage | AddressError

export type CoverageResponse = Record<string, CoverageResult>
