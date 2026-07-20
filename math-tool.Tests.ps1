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
        $result = pwsh -NoLogo -NoProfile -File "$PSScriptRoot/math-tool.ps1" -N 15
        $result | Should -Be 'Fibonacci(15) = 610'
    }

    It 'prints Fibonacci(0) = 0 when invoked with -N 0' {
        $result = pwsh -NoLogo -NoProfile -File "$PSScriptRoot/math-tool.ps1" -N 0
        $result | Should -Be 'Fibonacci(0) = 0'
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

Describe 'Get-Factorial' {
    BeforeAll {
        . "$PSScriptRoot/math-tool.ps1"
    }

    It 'returns 1 for N=0' {
        Get-Factorial -N 0 | Should -Be 1
    }

    It 'returns 1 for N=1' {
        Get-Factorial -N 1 | Should -Be 1
    }

    It 'returns 120 for N=5' {
        Get-Factorial -N 5 | Should -Be 120
    }

    It 'returns 2432902008176640000 for N=20' {
        Get-Factorial -N 20 | Should -Be 2432902008176640000
    }

    It 'throws for negative N' {
        { Get-Factorial -N -1 } | Should -Throw '*non-negative*'
    }
}

Describe 'Script execution' {
    It 'prints Fibonacci(10) = 55 when invoked with -Operation fibonacci -N 10' {
        $result = pwsh -NoLogo -NoProfile -File "$PSScriptRoot/math-tool.ps1" -Operation fibonacci -N 10
        $result | Should -Be 'Fibonacci(10) = 55'
    }

    It 'prints Factorial(5) = 120 when invoked with -Operation factorial -N 5' {
        $result = pwsh -NoLogo -NoProfile -File "$PSScriptRoot/math-tool.ps1" -Operation factorial -N 5
        $result | Should -Be 'Factorial(5) = 120'
    }
}

Describe 'Input validation' {
    It 'exits with non-zero code when -N is -1' {
        pwsh -NoLogo -NoProfile -File "$PSScriptRoot/math-tool.ps1" -N -1 2>&1 | Out-Null
        $LASTEXITCODE | Should -Not -Be 0
    }

    It 'exits with non-zero code when -N is 101' {
        pwsh -NoLogo -NoProfile -File "$PSScriptRoot/math-tool.ps1" -N 101 2>&1 | Out-Null
        $LASTEXITCODE | Should -Not -Be 0
    }
}

Describe 'Verbose output' {
    It 'includes Computing in verbose stream when -Verbose -N 5 is passed' {
        $result = & "$PSScriptRoot/math-tool.ps1" -Verbose -N 5 4>&1
        ($result | Out-String) | Should -Match 'Computing'
    }
}

Describe 'Help' {
    It 'returns help text containing SYNOPSIS' {
        $result = Get-Help "$PSScriptRoot/math-tool.ps1" | Out-String
        $result | Should -Match 'SYNOPSIS'
    }
}
