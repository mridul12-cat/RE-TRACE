// contracts/scripts/deploy.js — Deployment script for RETraceRegistry on Local Testnet
async function main() {
  const [deployer] = await ethers.getSigners();
  console.log("Deploying RETraceRegistry with account:", deployer.address);

  const RETraceRegistry = await ethers.getContractFactory("RETraceRegistry");
  const registry = await RETraceRegistry.deploy();
  await registry.waitForDeployment();

  const address = await registry.getAddress();
  console.log("RETraceRegistry deployed successfully to:", address);
  console.log("Network: LOCAL TESTNET (Chain ID: 31337)");
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error("Deployment failed:", error);
    process.exit(1);
  });
