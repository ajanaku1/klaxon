// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

interface IERC20 {
    function transfer(address to, uint256 amount) external returns (bool);
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
    function balanceOf(address) external view returns (uint256);
}

interface IOracle {
    function price() external view returns (uint256);
}

/// @notice Intentionally vulnerable demo pool. The exploit path is:
///
///   block N    : attacker calls oracle.bumpPrice(huge)  // collateral revalued up
///   block N+1  : attacker borrow()s far more than collateral is actually worth
///
/// The two-block gap is the detection window Klaxon agents race to close.
/// A reentrancy hole in `liquidate` is also left in place as a second
/// distinct exploit class for analyzer 1 (reentrancy) to flag.
contract VulnerableLendingPool {
    address public guardian;
    bool public paused;

    IERC20 public immutable collateral;
    IERC20 public immutable debtAsset;
    IOracle public oracle;

    mapping(address => uint256) public deposits;
    mapping(address => uint256) public debt;

    uint256 public constant LTV_BPS = 5000; // 50% LTV — borrow up to half oracle-priced collateral
    uint256 public constant BPS = 10000;

    event Deposited(address indexed user, uint256 amount);
    event Borrowed(address indexed user, uint256 amount, uint256 oraclePrice);
    event Liquidated(address indexed user, address indexed liquidator, uint256 seized);
    event PausedByGuardian();
    event Swept(address indexed token, address indexed to, uint256 amount);

    error IsPaused();
    error NotPaused();
    error NotGuardian();
    error Undercollateralized();
    error Healthy();

    modifier whenNotPaused() {
        if (paused) revert IsPaused();
        _;
    }

    constructor(address _collateral, address _debtAsset, address _oracle) {
        collateral = IERC20(_collateral);
        debtAsset = IERC20(_debtAsset);
        oracle = IOracle(_oracle);
    }

    function setGuardian(address _guardian) external {
        require(guardian == address(0), "guardian already set");
        guardian = _guardian;
    }

    function deposit(uint256 amount) external whenNotPaused {
        collateral.transferFrom(msg.sender, address(this), amount);
        deposits[msg.sender] += amount;
        emit Deposited(msg.sender, amount);
    }

    /// Borrow against oracle-valued collateral. Oracle is queried *now*, so
    /// a manipulated price in this same block lets the attacker drain.
    function borrow(uint256 amount) external whenNotPaused {
        uint256 p = oracle.price();
        uint256 collateralValue = (deposits[msg.sender] * p) / 1e18;
        uint256 maxBorrow = (collateralValue * LTV_BPS) / BPS;
        if (debt[msg.sender] + amount > maxBorrow) revert Undercollateralized();
        debt[msg.sender] += amount;
        debtAsset.transfer(msg.sender, amount);
        emit Borrowed(msg.sender, amount, p);
    }

    /// Reentrancy hole: external call before state cleared. Analyzer 1 should
    /// flag any tx where the trace shows liquidate() reentering pool methods.
    function liquidate(address user) external whenNotPaused {
        uint256 p = oracle.price();
        uint256 collateralValue = (deposits[user] * p) / 1e18;
        uint256 maxBorrow = (collateralValue * LTV_BPS) / BPS;
        if (debt[user] <= maxBorrow) revert Healthy();

        uint256 seized = deposits[user];
        collateral.transfer(msg.sender, seized);
        deposits[user] = 0;
        debt[user] = 0;
        emit Liquidated(user, msg.sender, seized);
    }

    /// Guardian-only pause. Idempotent.
    function pause() external {
        if (msg.sender != guardian) revert NotGuardian();
        paused = true;
        emit PausedByGuardian();
    }

    /// Guardian-only sweep of any token to a recovery address. Only valid
    /// while paused so it can't be used as a backdoor.
    function sweep(address to, address token) external {
        if (msg.sender != guardian) revert NotGuardian();
        if (!paused) revert NotPaused();
        uint256 bal = IERC20(token).balanceOf(address(this));
        IERC20(token).transfer(to, bal);
        emit Swept(token, to, bal);
    }
}
