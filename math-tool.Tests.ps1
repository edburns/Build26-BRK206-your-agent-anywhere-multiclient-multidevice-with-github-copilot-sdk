Describe 'Get-Fibonacci' {
    BeforeAll {
        . "$PSScriptRoot/math-tool.ps1"
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
