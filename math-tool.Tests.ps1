Describe 'Get-Fibonacci' {
    BeforeAll {
        . "$PSScriptRoot/math-tool.ps1"
    }

    It 'produces no output when dot-sourced' {
        $output = . "$PSScriptRoot/math-tool.ps1" *>&1
        $output | Should -BeNullOrEmpty
    }

    It 'prints Fibonacci(10) = 55 when invoked with no arguments' {
        $result = pwsh -NoLogo -NoProfile -File "$PSScriptRoot/math-tool.ps1"
        $result | Should -Be 'Fibonacci(10) = 55'
    }

    It 'prints Fibonacci(15) = 610 when invoked with -N 15' {
        $result = & "$PSScriptRoot/math-tool.ps1" -N 15
        $result | Should -Be 'Fibonacci(15) = 610'
    }

    It 'throws for negative N' {
        { Get-Fibonacci -N -1 } | Should -Throw '*non-negative*'
    }

    It 'returns 0 for N=0' {
        Get-Fibonacci -N 0 | Should -Be 0
    }

    It 'returns 1 for N=1' {
        Get-Fibonacci -N 1 | Should -Be 1
    }

    It 'returns 55 for N=10' {
        Get-Fibonacci -N 10 | Should -Be 55
    }

    It 'returns 6765 for N=20' {
        Get-Fibonacci -N 20 | Should -Be 6765
    }
}
